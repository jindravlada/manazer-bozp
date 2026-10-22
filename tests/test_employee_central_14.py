"""EMPLOYEE-CENTRAL-14: pořadí údajů ve výběru zaměstnance při přípravě zkoušky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-14-"))

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
        EXAMINER_MODE_NONE,
        EXAMINER_MODE_SINGLE,
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
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.ui.exam_person_combo import exam_person_choice_label
    from moduly.testy.ui.test_exam_prepare_dialog import TestExamPrepareDialog


class _Person:
    def __init__(self, **data):
        self.last_name = data.get("last_name", "")
        self.first_name = data.get("first_name", "")
        self.title_before = data.get("title_before", "")
        self.title_after = data.get("title_after", "")
        self.personal_number = data.get("personal_number", "")
        self.display_name = data.get("display_name", "")


class EmployeeCentral14TestCase(unittest.TestCase):
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

    def tearDown(self) -> None:
        for dialog in self.dialogs:
            dialog.close()

    def _worker(self, first: str, last: str, **extra):
        data = {
            "first_name": first,
            "last_name": last,
            "workplace_id": self.workplace.id,
            "responsibility_role_ids": [self.role.id],
            "active": True,
            "is_thp": False,
            "may_examine": False,
            "performs_controls": False,
            "personal_number": "",
            "title_before": "",
            "title_after": "",
        }
        data.update(extra)
        return settings_service.save_worker(**data)

    def test_label_omits_empty_parts_and_joins_titles(self) -> None:
        self.assertEqual(
            exam_person_choice_label(
                _Person(
                    last_name="Jindra",
                    first_name="Vladimír",
                    title_before="Ing.",
                    personal_number="60070068",
                )
            ),
            "Jindra | Vladimír | Ing. | 60070068",
        )
        self.assertEqual(
            exam_person_choice_label(
                _Person(
                    last_name="Horák",
                    first_name="Karel",
                    title_before="Ing.",
                    title_after="Ph.D.",
                    personal_number="9",
                )
            ),
            "Horák | Karel | Ing., Ph.D. | 9",
        )
        self.assertEqual(
            exam_person_choice_label(
                _Person(last_name="Novák", first_name="Jan", title_after="Ph.D.")
            ),
            "Novák | Jan | Ph.D.",
        )
        self.assertEqual(
            exam_person_choice_label(_Person(last_name="Novák", first_name="Jan")),
            "Novák | Jan",
        )
        self.assertNotIn(" |  | ", exam_person_choice_label(
            _Person(last_name="Novák", first_name="Jan", title_before="  ", personal_number="")
        ))
        self.assertFalse(
            exam_person_choice_label(_Person(last_name="Novák", first_name="Jan")).endswith("|")
        )

    def test_dialog_sorts_searches_and_keeps_incomplete_mark(self) -> None:
        self._worker("Eva", f"Dvořák{self.marker}")
        self._worker("Adam", f"Čech{self.marker}")
        self._worker("Adam", f"Dvořák{self.marker}")
        ready = self._worker(
            "Vladimír",
            "Jindra",
            title_before="Ing.",
            personal_number="60070068",
            may_examine=True,
        )
        self._worker("Jan", f"Novák{self.marker}")
        incomplete = self._worker(
            "Iva",
            f"Neúplná{self.marker}",
            workplace_id=None,
            responsibility_role_ids=[],
            title_before="Bc.",
        )
        topic = oral_question_topic_service.create_topic(name=f"Okruh {self.marker}")
        oral_question_service.create_question(topic_id=topic.id, text="Otázka")
        plain = test_definition_service.create_test(
            name=f"Bez {self.marker}",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(topic_id=topic.id, question_count=1)],
        )
        single = test_definition_service.create_test(
            name=f"Jeden {self.marker}",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_SINGLE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(topic_id=topic.id, question_count=1)],
        )
        historical = test_employee_service.create_employee(
            personal_number=f"H-{self.marker}",
            first_name="Jana",
            last_name=f"Historie{self.marker}",
            title_before="Bc.",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )
        old = test_exam_service.prepare_exam(
            employee_id=historical.id,
            test_id=plain.id,
            exam_date=date(2024, 6, 1),
        )
        before = (
            old.employee_display_name,
            old.employee_personal_number,
            old.employee_first_name,
            old.employee_last_name,
            old.employee_title_before,
        )

        dialog = TestExamPrepareDialog()
        self.dialogs.append(dialog)
        labels = [
            dialog.employee.itemText(index)
            for index in range(dialog.employee.count())
            if dialog.employee.itemText(index)
            and (
                self.marker in dialog.employee.itemText(index)
                or "Jindra" in dialog.employee.itemText(index)
            )
        ]
        self.assertEqual(
            labels,
            [
                f"Čech{self.marker} | Adam",
                f"Dvořák{self.marker} | Adam",
                f"Dvořák{self.marker} | Eva",
                "Jindra | Vladimír | Ing. | 60070068",
                f"Neúplná{self.marker} | Iva | Bc. (Chybí provoz a funkce / role.)",
                f"Novák{self.marker} | Jan",
            ],
        )
        blocked = next(text for text in labels if "Neúplná" in text)
        blocked_index = dialog.employee.findText(blocked)
        item = dialog.employee.model().item(blocked_index)
        assert item is not None
        self.assertFalse(item.flags() & Qt.ItemFlag.ItemIsEnabled)
        self.assertNotIn(incomplete.id, dialog.employee._ids.values())

        completer = dialog.employee.completer()
        for prefix in ("vladimír", "jindra", "ing.", "60070068"):
            completer.setCompletionPrefix(prefix)
            self.assertGreater(completer.completionCount(), 0, prefix)
        for combo in (dialog.examiner, dialog.chair, dialog.member):
            texts = [combo.itemText(index) for index in range(combo.count())]
            self.assertIn("Jindra | Vladimír | Ing. | 60070068", texts)
        dialog.employee.setCurrentText("Jindra | Vladimír | Ing. | 60070068")
        self.assertEqual(dialog.employee.person_id(), ready.id)
        dialog.test.setCurrentIndex(dialog.test.findData(single.id))

        kept = test_exam_service.get_exam(old.id)
        assert kept is not None
        self.assertEqual(
            (
                kept.employee_display_name,
                kept.employee_personal_number,
                kept.employee_first_name,
                kept.employee_last_name,
                kept.employee_title_before,
            ),
            before,
        )
        self.assertEqual(kept.employee_display_name, historical.display_name)
        self.assertNotIn("|", kept.employee_display_name)
