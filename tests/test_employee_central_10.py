"""EMPLOYEE-CENTRAL-10: dialog přípravy zkoušky bere centrální zaměstnance."""

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

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-10-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QMessageBox

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.employee_central_link_service import (
        employee_central_link_service,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        EMPLOYEE_SOURCE_THP_WORKER,
        EXAM_ROLE_CHAIR,
        EXAM_ROLE_EXAMINER,
        EXAM_ROLE_MEMBER,
        EXAMINER_MODE_COMMISSION,
        EXAMINER_MODE_SINGLE,
        VALIDITY_UNIT_YEARS,
    )
    from moduly.testy.sluzby.exam_validity_service import exam_validity_service
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import (
        oral_question_topic_service,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
    from moduly.testy.ui.test_exam_prepare_dialog import TestExamPrepareDialog


class EmployeeCentral10TestCase(unittest.TestCase):
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
        self.single_test = test_definition_service.create_test(
            name=f"Jeden {self.marker}",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_SINGLE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(topic_id=topic.id, question_count=1)],
        )
        self.commission_test = test_definition_service.create_test(
            name=f"Komise {self.marker}",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_COMMISSION,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(topic_id=topic.id, question_count=1)],
        )

    def tearDown(self) -> None:
        for dialog in self.dialogs:
            dialog.close()

    def _dialog(self) -> TestExamPrepareDialog:
        dialog = TestExamPrepareDialog()
        self.dialogs.append(dialog)
        return dialog

    def _worker(self, number: str, first: str, last: str, **extra):
        data = {
            "first_name": first,
            "last_name": last,
            "personal_number": number,
            "title_before": "Ing.",
            "position": f"Svářeč {self.marker}",
            "workplace_id": self.workplace.id,
            "responsibility_role_ids": [self.role.id],
            "active": True,
            "is_thp": False,
            "may_examine": False,
            "performs_controls": False,
        }
        data.update(extra)
        return settings_service.save_worker(**data)

    def _label(self, person) -> str:
        return f"{person.personal_number} – {person.display_name}"

    def _ids(self, combo) -> set[int]:
        return set(combo._ids.values())

    def _employee_count(self) -> int:
        connection = sqlite3.connect(str(storage_module.storage_service.database_path))
        try:
            return int(connection.execute("SELECT COUNT(*) FROM test_employees").fetchone()[0])
        finally:
            connection.close()

    def test_dialog_offers_active_workers_and_prepares_central_exam(self) -> None:
        active = self._worker(f"A-{self.marker}", "Eva", f"Aktivní{self.marker}")
        inactive = self._worker(
            f"N-{self.marker}",
            "Nora",
            f"Neaktivní{self.marker}",
            active=False,
        )
        examiner = self._worker(
            f"E-{self.marker}",
            "Adam",
            f"Zkouší{self.marker}",
            may_examine=True,
        )
        plain = self._worker(f"P-{self.marker}", "Iva", f"Bezpráva{self.marker}")
        chair = self._worker(
            f"C-{self.marker}",
            "Ota",
            f"Předsedá{self.marker}",
            may_examine=True,
        )
        member = self._worker(
            f"M-{self.marker}",
            "Lea",
            f"Člen{self.marker}",
            may_examine=True,
        )
        historical = test_employee_service.create_employee(
            personal_number=f"H-{self.marker}",
            first_name="Jana",
            last_name=f"Historie{self.marker}",
            title_before="Bc.",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
            may_examine=False,
            active=True,
        )
        historical_examiner = test_employee_service.create_employee(
            personal_number=f"HE-{self.marker}",
            first_name="Petr",
            last_name=f"Zkouší{self.marker}",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
            may_examine=True,
            active=True,
        )
        employees_before = self._employee_count()
        old_exam = test_exam_service.prepare_exam(
            employee_id=historical.id,
            test_id=self.single_test.id,
            exam_date=date(2024, 6, 1),
            examiner_id=historical_examiner.id,
        )
        before = (
            old_exam.employee_id,
            old_exam.employee_source,
            old_exam.employee_display_name,
            old_exam.employee_personal_number,
            old_exam.employee_roles_text,
        )

        dialog = self._dialog()
        offered = self._ids(dialog.employee)
        self.assertEqual(
            offered,
            {active.id, examiner.id, plain.id, chair.id, member.id},
        )
        for combo in (dialog.examiner, dialog.chair, dialog.member):
            examiners = self._ids(combo)
            self.assertIn(examiner.id, examiners)
            self.assertIn(chair.id, examiners)
            self.assertNotIn(plain.id, examiners)
            self.assertNotIn(inactive.id, examiners)
            self.assertNotIn(active.id, examiners)

        dialog.employee.setCurrentText(self._label(active))
        dialog.examiner.setCurrentText(self._label(examiner))
        dialog.test.setCurrentIndex(dialog.test.findData(self.single_test.id))
        dialog.exam_date.setDate(QDate(2026, 5, 4))
        self.assertEqual(dialog.get_data()["employee_source"], EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(dialog.get_data()["examiner_source"], EMPLOYEE_SOURCE_THP_WORKER)
        dialog.accept()
        self.assertIsNotNone(dialog.saved_exam_id)
        stored = test_exam_service.get_exam(dialog.saved_exam_id)
        assert stored is not None
        self.assertEqual(stored.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(stored.employee_id, active.id)
        self.assertEqual(stored.employee_personal_number, f"A-{self.marker}")
        self.assertEqual(stored.employee_display_name, active.display_name)
        self.assertEqual(stored.employee_workplace_name, self.workplace.name)
        self.assertEqual(stored.employee_roles_text, f"Mistr {self.marker}")
        self.assertNotIn(f"Svářeč {self.marker}", stored.employee_roles_text)
        people = test_exam_service.get_examiners(stored.id)
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(people[0].employee_id, examiner.id)
        self.assertEqual(people[0].role, EXAM_ROLE_EXAMINER)
        self.assertEqual(people[0].display_name, examiner.display_name)

        commission = self._dialog()
        commission.employee.setCurrentText(self._label(active))
        commission.test.setCurrentIndex(commission.test.findData(self.commission_test.id))
        commission.chair.setCurrentText(self._label(chair))
        commission.member.setCurrentText(self._label(member))
        commission._add_member()
        commission.exam_date.setDate(QDate(2026, 5, 5))
        commission.accept()
        board = test_exam_service.get_examiners(commission.saved_exam_id)
        self.assertEqual(
            [(person.role, person.position, person.employee_id, person.employee_source) for person in board],
            [
                (EXAM_ROLE_CHAIR, 1, chair.id, EMPLOYEE_SOURCE_THP_WORKER),
                (EXAM_ROLE_MEMBER, 2, member.id, EMPLOYEE_SOURCE_THP_WORKER),
            ],
        )

        kept = test_exam_service.get_exam(old_exam.id)
        assert kept is not None
        self.assertEqual(
            (
                kept.employee_id,
                kept.employee_source,
                kept.employee_display_name,
                kept.employee_personal_number,
                kept.employee_roles_text,
            ),
            before,
        )
        self.assertEqual(kept.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertEqual(self._employee_count(), employees_before)

        employee_central_link_service.link_existing(
            test_employee_id=historical.id,
            thp_worker_id=active.id,
        )
        rows = [
            row
            for row in exam_validity_service.list_rows(
                today=date(2026, 5, 6),
                include_inactive_employees=True,
            )
            if row.test_definition_id == self.single_test.id
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].employee_id, active.id)
        self.assertEqual(rows[0].employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertTrue(rows[0].tracked)
        self.assertGreaterEqual(rows[0].prepared_count, 2)

    def test_incomplete_worker_and_self_exam_show_warning(self) -> None:
        examiner = self._worker(
            f"E-{self.marker}",
            "Adam",
            f"Zkouší{self.marker}",
            may_examine=True,
        )
        incomplete = self._worker(
            f"X-{self.marker}",
            "Eva",
            f"Neúplná{self.marker}",
            personal_number="",
        )
        employees_before = self._employee_count()
        dialog = self._dialog()
        dialog.employee.setCurrentText(incomplete.display_name)
        dialog.examiner.setCurrentText(self._label(examiner))
        dialog.test.setCurrentIndex(dialog.test.findData(self.single_test.id))
        with patch.object(QMessageBox, "warning") as warning:
            dialog.accept()
        warning.assert_called()
        self.assertIn("osobní číslo", warning.call_args.args[2])
        self.assertIsNone(dialog.saved_exam_id)
        self.assertEqual(self._employee_count(), employees_before)

        complete = self._worker(
            f"S-{self.marker}",
            "Eva",
            f"Sama{self.marker}",
            may_examine=True,
        )
        blocked = self._dialog()
        blocked.employee.setCurrentText(self._label(complete))
        self.assertNotIn(complete.id, self._ids(blocked.examiner))
        with self.assertRaises(TestExamError) as caught:
            test_exam_service.prepare_exam(
                employee_id=complete.id,
                employee_source=EMPLOYEE_SOURCE_THP_WORKER,
                examiner_source=EMPLOYEE_SOURCE_THP_WORKER,
                test_id=self.single_test.id,
                exam_date=date(2026, 5, 4),
                examiner_id=complete.id,
            )
        self.assertIn("nemůže být současně zkoušejícím", str(caught.exception))
        self.assertEqual(self._employee_count(), employees_before)
