"""EMPLOYEE-CENTRAL-18: příprava zkoušky bez tichého zdroje test_employee."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-18-"))
_EXAM_DAY = date(2026, 10, 22)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication
    from sqlalchemy import func, select

    from core.database.session import get_session
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_TEXT,
        EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        EMPLOYEE_SOURCE_THP_WORKER,
        EXAM_ROLE_EXAMINER,
        EXAMINER_MODE_NONE,
        EXAMINER_MODE_SINGLE,
        VALIDITY_UNIT_YEARS,
    )
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.paper_batch_dialog import PaperBatchDialog
    from moduly.testy.ui.test_exam_prepare_dialog import TestExamPrepareDialog


def _exam_count() -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(TestExam)) or 0)


class EmployeeCentral18TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.dialogs = []
        self.workplace = settings_service.save_workplace(name=f"Hala {self.marker}")
        self.role = responsibility_role_service.create_role(name=f"Mistr {self.marker}")

    def tearDown(self) -> None:
        for dialog in self.dialogs:
            dialog.close()

    def test_sources_are_required_and_same_id_stays_distinct(self) -> None:
        examinee = self._worker("Vladimír", "Jindra", personal_number=f"e{self.marker}")
        examiner = self._worker(
            "Adam",
            "Zkoušející",
            personal_number=f"z{self.marker}",
            may_examine=True,
        )
        self._alias(examinee.id, f"t{self.marker}", "Cizí", "Evidence")
        self._alias(examiner.id, f"x{self.marker}", "Jiný", "Protokol", may_examine=True)
        single = self._written_test(EXAMINER_MODE_SINGLE)
        plain = self._written_test(EXAMINER_MODE_NONE)

        before = _exam_count()
        with self.assertRaises(TypeError) as missing_employee:
            test_exam_service.prepare_exam(
                employee_id=examinee.id,
                test_id=single.id,
                exam_date=_EXAM_DAY,
                examiner_id=examiner.id,
                examiner_source=EMPLOYEE_SOURCE_THP_WORKER,
            )
        self.assertIn("employee_source", str(missing_employee.exception))
        with self.assertRaises(TypeError) as missing_examiner:
            test_exam_service.prepare_exam(
                employee_id=examinee.id,
                employee_source=EMPLOYEE_SOURCE_THP_WORKER,
                test_id=single.id,
                exam_date=_EXAM_DAY,
                examiner_id=examiner.id,
            )
        self.assertIn("examiner_source", str(missing_examiner.exception))
        with self.assertRaises(TestExamError) as unknown:
            test_exam_service.prepare_exam(
                employee_id=examinee.id,
                employee_source="",
                examiner_source=EMPLOYEE_SOURCE_THP_WORKER,
                test_id=single.id,
                exam_date=_EXAM_DAY,
                examiner_id=examiner.id,
            )
        self.assertIn("Neznámý zdroj zaměstnance.", str(unknown.exception))
        self.assertEqual(_exam_count(), before)

        historical = test_exam_service.prepare_exam(
            employee_id=examinee.id,
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            test_id=single.id,
            exam_date=_EXAM_DAY,
            examiner_id=examiner.id,
        )
        historical_snapshot = (
            historical.employee_source,
            historical.employee_id,
            historical.employee_last_name,
            historical.employee_display_name,
        )
        historical_examiner = test_exam_service.get_examiners(historical.id)[0]
        self.assertEqual(historical.employee_last_name, "Evidence")
        self.assertEqual(historical_examiner.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertIn("Jiný", historical_examiner.display_name)

        created = test_exam_service.prepare_exam(
            employee_id=examinee.id,
            employee_source=EMPLOYEE_SOURCE_THP_WORKER,
            examiner_source=EMPLOYEE_SOURCE_THP_WORKER,
            test_id=single.id,
            exam_date=_EXAM_DAY,
            examiner_id=examiner.id,
        )
        self.assertEqual(created.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(created.employee_id, examinee.id)
        self.assertEqual(created.employee_last_name, "Jindra")
        people = test_exam_service.get_examiners(created.id)
        self.assertEqual(
            [(person.role, person.employee_id, person.employee_source) for person in people],
            [(EXAM_ROLE_EXAMINER, examiner.id, EMPLOYEE_SOURCE_THP_WORKER)],
        )
        self.assertIn("Adam", people[0].display_name)
        self.assertNotIn("Jiný", people[0].display_name)

        batch = test_exam_service.prepare_paper_batch(
            employee_ids=[examinee.id],
            test_id=plain.id,
            exam_date=_EXAM_DAY,
        )
        self.assertEqual(batch[0].employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(batch[0].employee_last_name, "Jindra")

        fresh = test_exam_service.get_exam(historical.id)
        self.assertEqual(
            (
                fresh.employee_source,
                fresh.employee_id,
                fresh.employee_last_name,
                fresh.employee_display_name,
            ),
            historical_snapshot,
        )
        fresh_examiner = test_exam_service.get_examiners(fresh.id)[0]
        self.assertEqual(fresh_examiner.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertEqual(fresh_examiner.display_name, historical_examiner.display_name)

        prepare = TestExamPrepareDialog()
        batch_dialog = PaperBatchDialog()
        self.dialogs.extend((prepare, batch_dialog))
        data = prepare.get_data()
        self.assertEqual(data["employee_source"], EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(data["examiner_source"], EMPLOYEE_SOURCE_THP_WORKER)

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
        }
        data.update(extra)
        return settings_service.save_worker(**data)

    def _alias(self, person_id: int, number: str, first: str, last: str, *, may_examine: bool = False) -> None:
        with get_session() as session:
            session.add(
                TestEmployee(
                    id=person_id,
                    personal_number=number,
                    first_name=first,
                    last_name=last,
                    title_before="",
                    title_after="",
                    workplace_id=self.workplace.id,
                    may_examine=may_examine,
                    active=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )
            session.commit()

    def _written_test(self, examiner_mode: str):
        topic = written_question_topic_service.create_topic(
            name=f"Okruh {self.marker} {examiner_mode}"
        )
        written_question_service.create_question(
            topic_id=topic.id,
            text="Jaký je postup?",
            answer_kind=ANSWER_KIND_TEXT,
            answers=[
                WrittenAnswerInput(text="první", is_correct=True),
                WrittenAnswerInput(text="druhá"),
                WrittenAnswerInput(text="třetí"),
            ],
        )
        return test_definition_service.create_test(
            name=f"Test {self.marker} {examiner_mode}",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=examiner_mode,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
