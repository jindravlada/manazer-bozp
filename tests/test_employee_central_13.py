"""EMPLOYEE-CENTRAL-13: připravenost zaměstnance ke zkoušce bez povinného osobního čísla."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-13-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        EMPLOYEE_SOURCE_THP_WORKER,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
    )
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import (
        oral_question_topic_service,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from tests.historical_test_employee import (
        seed_historical_test_employee,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import (
        TestExamError,
        format_central_employee_gaps,
        test_exam_service,
    )
    from moduly.testy.ui.test_exam_prepare_dialog import TestExamPrepareDialog


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(storage_module.storage_service.database_path))
    connection.row_factory = sqlite3.Row
    return connection


class EmployeeCentral13TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.dialogs: list[TestExamPrepareDialog] = []
        self.workplace = settings_service.save_workplace(
            name=f"Provoz {self.marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.role = responsibility_role_service.create_role(name=f"Mistr {self.marker}")
        topic = oral_question_topic_service.create_topic(name=f"Okruh {self.marker}")
        oral_question_service.create_question(topic_id=topic.id, text=f"Otázka {self.marker}")
        self.test = test_definition_service.create_test(
            name=f"Zkouška {self.marker}",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(topic_id=topic.id, question_count=1)],
        )

    def tearDown(self) -> None:
        for dialog in self.dialogs:
            dialog.close()

    def _worker(self, first: str, last: str, **extra):
        data = {
            "first_name": first,
            "last_name": last,
            "title_before": "Ing.",
            "personal_number": "",
            "workplace_id": self.workplace.id,
            "responsibility_role_ids": [self.role.id],
            "active": True,
            "is_thp": False,
            "may_examine": False,
            "performs_controls": False,
            "position": f"Svářeč {self.marker}",
        }
        data.update(extra)
        return settings_service.save_worker(**data)

    def _prepare(self, worker_id: int):
        return test_exam_service.prepare_exam(
            employee_id=worker_id,
            employee_source=EMPLOYEE_SOURCE_THP_WORKER,
            test_id=self.test.id,
            exam_date=date(2026, 5, 4),
            examiner_source=EMPLOYEE_SOURCE_THP_WORKER,
        )

    def _dialog(self) -> TestExamPrepareDialog:
        dialog = TestExamPrepareDialog()
        self.dialogs.append(dialog)
        return dialog

    def _combo_index(self, dialog: TestExamPrepareDialog, text: str) -> int:
        for index in range(dialog.employee.count()):
            if text in dialog.employee.itemText(index):
                return index
        raise AssertionError(text)

    def test_prepare_keeps_optional_personal_number_and_refuses_gaps(self) -> None:
        historical = seed_historical_test_employee(
            personal_number=f"H-{self.marker}",
            first_name="Jana",
            last_name=f"Historie{self.marker}",
            title_before="Bc.",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )
        old = test_exam_service.prepare_exam(
            employee_id=historical.id,
            test_id=self.test.id,
            exam_date=date(2024, 6, 1),
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        )
        before = (
            old.employee_id,
            old.employee_source,
            old.employee_personal_number,
            old.employee_display_name,
            old.employee_roles_text,
        )

        without_number = self._worker("Eva", f"Bezčísla{self.marker}")
        stored = self._prepare(without_number.id)
        self.assertEqual(stored.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(stored.employee_id, without_number.id)
        self.assertEqual(stored.employee_personal_number, "")
        self.assertEqual(stored.employee_first_name, "Eva")
        self.assertEqual(stored.employee_last_name, f"Bezčísla{self.marker}")
        self.assertEqual(stored.employee_workplace_name, self.workplace.name)
        self.assertEqual(stored.employee_roles_text, f"Mistr {self.marker}")
        self.assertNotIn(f"Svářeč {self.marker}", stored.employee_roles_text)

        with_number = self._worker(
            "Adam",
            f"Sčíslem{self.marker}",
            personal_number=f"C-{self.marker}",
        )
        numbered = self._prepare(with_number.id)
        self.assertEqual(numbered.employee_personal_number, f"C-{self.marker}")

        missing_place = self._worker(
            "Iva",
            f"Bezprovozu{self.marker}",
            workplace_id=None,
        )
        with self.assertRaises(TestExamError) as place_error:
            self._prepare(missing_place.id)
        self.assertIn("přiřazený provoz", str(place_error.exception))

        missing_role = self._worker(
            "Lea",
            f"Bezrole{self.marker}",
            responsibility_role_ids=[],
        )
        with self.assertRaises(TestExamError) as role_error:
            self._prepare(missing_role.id)
        self.assertIn("funkci / roli", str(role_error.exception))

        inactive = self._worker("Nora", f"Neaktivní{self.marker}", active=False)
        with self.assertRaises(TestExamError) as inactive_error:
            self._prepare(inactive.id)
        self.assertIn("aktivního zaměstnance", str(inactive_error.exception))

        nameless = self._worker("Ota", f"Bezejména{self.marker}")
        connection = _connect()
        try:
            connection.execute(
                "UPDATE thp_workers SET first_name = '' WHERE id = ?",
                (nameless.id,),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(TestExamError) as name_error:
            self._prepare(nameless.id)
        self.assertIn("jméno a příjmení", str(name_error.exception))

        kept = test_exam_service.get_exam(old.id)
        assert kept is not None
        self.assertEqual(
            (
                kept.employee_id,
                kept.employee_source,
                kept.employee_personal_number,
                kept.employee_display_name,
                kept.employee_roles_text,
            ),
            before,
        )
        self.assertEqual(kept.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)

    def test_gap_notice_uses_nominative_for_every_combination(self) -> None:
        name = "jméno a příjmení"
        workplace = "provoz"
        role = "funkce / role"
        self.assertEqual(format_central_employee_gaps([]), "")
        self.assertEqual(format_central_employee_gaps([name]), "Chybí jméno a příjmení.")
        self.assertEqual(format_central_employee_gaps([workplace]), "Chybí provoz.")
        self.assertEqual(format_central_employee_gaps([role]), "Chybí funkce / role.")
        self.assertEqual(
            format_central_employee_gaps([name, workplace]),
            "Chybí jméno a příjmení a provoz.",
        )
        self.assertEqual(
            format_central_employee_gaps([name, role]),
            "Chybí jméno a příjmení a funkce / role.",
        )
        self.assertEqual(
            format_central_employee_gaps([workplace, role]),
            "Chybí provoz a funkce / role.",
        )
        self.assertEqual(
            format_central_employee_gaps([name, workplace, role]),
            "Chybí jméno a příjmení, provoz a funkce / role.",
        )

    def test_dialog_shows_incomplete_workers_and_hides_inactive(self) -> None:
        ready = self._worker("Eva", f"Hotová{self.marker}")
        incomplete = self._worker(
            "Iva",
            f"Neúplná{self.marker}",
            workplace_id=None,
            responsibility_role_ids=[],
        )
        inactive = self._worker("Nora", f"Neaktivní{self.marker}", active=False)
        dialog = self._dialog()
        texts = [dialog.employee.itemText(index) for index in range(dialog.employee.count())]
        self.assertTrue(any(f"Hotová{self.marker}" in text for text in texts))
        self.assertFalse(any(f"Neaktivní{self.marker}" in text for text in texts))
        index = self._combo_index(dialog, f"Neúplná{self.marker}")
        label = dialog.employee.itemText(index)
        self.assertIn("Chybí provoz a funkce / role.", label)
        item = dialog.employee.model().item(index)
        assert item is not None
        self.assertFalse(item.flags() & Qt.ItemFlag.ItemIsEnabled)
        self.assertIn(ready.id, dialog.employee._ids.values())
        self.assertNotIn(incomplete.id, dialog.employee._ids.values())
        self.assertNotIn(inactive.id, dialog.employee._ids.values())
        dialog.employee.setCurrentText(label)
        self.assertEqual(dialog.employee_hint.text(), "Chybí provoz a funkce / role.")
        self.assertFalse(dialog.employee_hint.isHidden())

        ready_label = dialog.employee.itemText(self._combo_index(dialog, f"Hotová{self.marker}"))
        self.assertNotIn("Chybí", ready_label)
        dialog.employee.setCurrentText(ready_label)
        self.assertEqual(dialog.employee.person_id(), ready.id)
        self.assertTrue(dialog.employee_hint.isHidden())
        dialog.test.setCurrentIndex(dialog.test.findData(self.test.id))
        dialog.accept()
        self.assertIsNotNone(dialog.saved_exam_id)
        created = test_exam_service.get_exam(dialog.saved_exam_id)
        assert created is not None
        self.assertEqual(created.employee_personal_number, "")
        self.assertEqual(created.employee_id, ready.id)
