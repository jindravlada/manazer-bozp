"""EMPLOYEE-CENTRAL-15: hromadná příprava papírových testů z centrální evidence."""

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

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-15-"))
_EXAM_DAY = date(2026, 10, 22)

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
    from sqlalchemy import delete, func, select

    from core.database.session import get_session
    from core.utils.czech_sort import czech_sorted, worker_sort_key
    from moduly.nastaveni.modely.test_employee_central_link import (
        TestEmployeeCentralLink,
    )
    from moduly.nastaveni.modely.thp_worker import ThpWorker
    from moduly.nastaveni.modely.thp_worker_role import ThpWorkerRole
    from moduly.nastaveni.sluzby.employee_central_link_service import (
        employee_central_link_service,
    )
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
    from moduly.testy.modely.test_definition import TestDefinition
    from moduly.testy.modely.test_definition_oral_topic import TestDefinitionOralTopic
    from moduly.testy.modely.test_definition_written_topic import (
        TestDefinitionWrittenTopic,
    )
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.modely.test_exam_examiner import TestExamExaminer
    from moduly.testy.modely.test_exam_oral_question import TestExamOralQuestion
    from moduly.testy.modely.test_exam_validity_tracking import TestExamValidityTracking
    from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
    from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.modely.written_question import WrittenQuestion
    from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.exam_validity_service import exam_validity_service
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
        TestExamService,
        test_exam_service,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.exam_person_combo import exam_person_choice_label
    from moduly.testy.ui.paper_batch_dialog import PaperBatchDialog


def _wipe() -> None:
    with get_session() as session:
        session.execute(delete(TestExamWrittenChoice))
        session.execute(delete(TestExamWrittenAnswer))
        session.execute(delete(TestExamWrittenQuestion))
        session.execute(delete(TestExamOralQuestion))
        session.execute(delete(TestExamExaminer))
        session.execute(delete(TestExam))
        session.execute(delete(TestExamValidityTracking))
        session.execute(delete(TestDefinitionWrittenTopic))
        session.execute(delete(TestDefinitionOralTopic))
        session.execute(delete(TestDefinition))
        session.execute(delete(WrittenQuestionAnswer))
        session.execute(delete(WrittenQuestion))
        session.execute(delete(WrittenQuestionTopic))
        session.execute(delete(TestEmployeeCentralLink))
        session.execute(delete(TestEmployeeRole))
        session.execute(delete(TestEmployee))
        session.execute(delete(ThpWorkerRole))
        session.execute(delete(ThpWorker))
        session.commit()


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


class EmployeeCentral15TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _wipe()
        self.marker = uuid.uuid4().hex[:8]
        self.dialogs: list[PaperBatchDialog] = []
        self.workplace = settings_service.save_workplace(name=f"Hala {self.marker}")
        self.other_workplace = settings_service.save_workplace(name=f"Dílna {self.marker}")
        self.role = responsibility_role_service.create_role(name=f"Mistr {self.marker}")

    def tearDown(self) -> None:
        for dialog in self.dialogs:
            dialog.close()

    def test_dialog_lists_active_workers_in_czech_order_and_blocks_incomplete(self) -> None:
        cech = self._worker("Adam", "Čech", personal_number=f"15{self.marker[:4]}1")
        dvorak = self._worker("Bořek", "Dvořák", personal_number=f"15{self.marker[:4]}2")
        chladek = self._worker(
            "Cyril",
            "Chládek",
            personal_number=f"15{self.marker[:4]}3",
            title_before="Ing.",
        )
        novak = self._worker("Dana", "Novák", personal_number="")
        incomplete = self._worker(
            "Eva",
            "Neúplná",
            personal_number=f"15{self.marker[:4]}4",
            workplace_id=None,
            responsibility_role_ids=[],
        )
        inactive = self._worker(
            "Filip",
            "Neaktivní",
            personal_number=f"15{self.marker[:4]}5",
            active=False,
        )
        examiner = self._worker(
            "Vladimír",
            "Jindra",
            personal_number="60070068",
            title_before="Ing.",
            may_examine=True,
        )
        dialog = self._dialog()
        labels = [
            dialog.employees.item(row, 1).text()
            for row in range(dialog.employees.rowCount())
        ]
        expected = [
            exam_person_choice_label(person)
            for person in czech_sorted(
                [cech, dvorak, chladek, novak, incomplete, examiner],
                key=worker_sort_key,
            )
        ]
        incomplete_label = exam_person_choice_label(incomplete)
        expected = [
            f"{label} (Chybí provoz a funkce / role.)" if label == incomplete_label else label
            for label in expected
        ]
        self.assertEqual(labels, expected)
        self.assertTrue(any(label.startswith("Čech | Adam") for label in labels))
        self.assertTrue(any(label.startswith("Chládek | Cyril | Ing.") for label in labels))
        self.assertIn("Jindra | Vladimír | Ing. | 60070068", labels)
        self.assertNotIn("Neaktivní", "\n".join(labels))
        self.assertNotEqual(inactive.id, incomplete.id)

        incomplete_row = labels.index(f"{incomplete_label} (Chybí provoz a funkce / role.)")
        flag = dialog.employees.item(incomplete_row, 0).flags()
        self.assertFalse(flag & Qt.ItemFlag.ItemIsUserCheckable)
        dialog.select_visible_btn.click()
        selected = dialog.selected_employee_ids()
        self.assertIn(cech.id, selected)
        self.assertIn(novak.id, selected)
        self.assertNotIn(incomplete.id, selected)
        self.assertNotIn(inactive.id, selected)

        dialog.search.setText("Chládek")
        visible = [
            dialog.employees.item(row, 1).text()
            for row in range(dialog.employees.rowCount())
            if not dialog.employees.isRowHidden(row)
        ]
        self.assertEqual(visible, [exam_person_choice_label(chladek)])
        dialog.search.clear()
        moved = self._worker(
            "Gustav",
            "Dílnař",
            personal_number=f"15{self.marker[:4]}6",
            workplace_id=self.other_workplace.id,
        )
        dialog._load_employees()
        dialog.workplace.setCurrentIndex(self._workplace_index(dialog, self.other_workplace.name))
        visible_ids = [
            int(dialog.employees.item(row, 0).data(Qt.ItemDataRole.UserRole))
            for row in range(dialog.employees.rowCount())
            if not dialog.employees.isRowHidden(row)
        ]
        self.assertEqual(visible_ids, [moved.id])

        examiner_labels = [
            dialog.examiner.itemText(index) for index in range(dialog.examiner.count())
        ]
        self.assertIn("Jindra | Vladimír | Ing. | 60070068", examiner_labels)
        self.assertNotIn("Čech | Adam", examiner_labels)

    def test_batch_prepares_central_exams_with_snapshots(self) -> None:
        named = self._worker(
            "Vladimír",
            "Jindra",
            personal_number="60070068",
            title_before="Ing.",
            position="Vedoucí směny",
        )
        unnamed = self._worker("Eva", "Malá", personal_number="")
        examiner = self._worker(
            "Adam",
            "Zkoušející",
            personal_number=f"zk{self.marker[:4]}",
            may_examine=True,
        )
        definition = self._written_test(EXAMINER_MODE_SINGLE)
        employees_before = _count(TestEmployee)
        links_before = _count(TestEmployeeCentralLink)
        created = test_exam_service.prepare_paper_batch(
            employee_ids=[named.id, unnamed.id],
            test_id=definition.id,
            exam_date=_EXAM_DAY,
            examiner_id=examiner.id,
        )
        self.assertEqual(len(created), 2)
        by_id = {int(exam.employee_id): exam for exam in created}
        self.assertEqual(set(by_id), {named.id, unnamed.id})
        for exam in created:
            self.assertEqual(exam.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
            self.assertEqual(exam.employee_workplace_name, self.workplace.name)
            self.assertEqual(exam.employee_roles_text, self.role.name)
            self.assertNotIn("Vedoucí směny", exam.employee_roles_text)
            people = test_exam_service.get_examiners(exam.id)
            self.assertEqual(
                [(person.role, person.employee_id, person.employee_source) for person in people],
                [(EXAM_ROLE_EXAMINER, examiner.id, EMPLOYEE_SOURCE_THP_WORKER)],
            )
        self.assertEqual(by_id[named.id].employee_last_name, "Jindra")
        self.assertEqual(by_id[named.id].employee_first_name, "Vladimír")
        self.assertEqual(by_id[named.id].employee_title_before, "Ing.")
        self.assertEqual(by_id[named.id].employee_personal_number, "60070068")
        self.assertEqual(by_id[unnamed.id].employee_personal_number, "")
        self.assertEqual(by_id[unnamed.id].employee_display_name, "Eva Malá")
        self.assertEqual(_count(TestEmployee), employees_before)
        self.assertEqual(_count(TestEmployeeCentralLink), links_before)

    def test_same_numeric_id_does_not_swap_people_and_history_stays(self) -> None:
        worker = self._worker("Vladimír", "Jindra", personal_number=f"w{self.marker}")
        historical_employee = TestEmployee(
            id=worker.id,
            personal_number=f"t{self.marker}",
            first_name="Cizí",
            last_name="Evidence",
            title_before="",
            title_after="",
            workplace_id=self.workplace.id,
            may_examine=False,
            active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        with get_session() as session:
            session.add(historical_employee)
            session.commit()
        definition = self._written_test(EXAMINER_MODE_NONE)
        historical = test_exam_service.prepare_exam(
            employee_id=worker.id,
            test_id=definition.id,
            exam_date=_EXAM_DAY,
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        )
        historical_snapshot = (
            historical.employee_source,
            historical.employee_id,
            historical.employee_first_name,
            historical.employee_last_name,
            historical.employee_personal_number,
            historical.employee_display_name,
            historical.employee_roles_text,
        )
        created = test_exam_service.prepare_paper_batch(
            employee_ids=[worker.id],
            test_id=definition.id,
            exam_date=_EXAM_DAY,
        )
        self.assertEqual(len(created), 1)
        fresh = test_exam_service.get_exam(historical.id)
        self.assertEqual(
            (
                fresh.employee_source,
                fresh.employee_id,
                fresh.employee_first_name,
                fresh.employee_last_name,
                fresh.employee_personal_number,
                fresh.employee_display_name,
                fresh.employee_roles_text,
            ),
            historical_snapshot,
        )
        self.assertEqual(fresh.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertEqual(fresh.employee_last_name, "Evidence")
        new_exam = created[0]
        self.assertEqual(new_exam.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(new_exam.employee_id, worker.id)
        self.assertEqual(new_exam.employee_last_name, "Jindra")
        self.assertNotEqual(new_exam.id, historical.id)
        rows = [
            row
            for row in exam_validity_service.list_rows(today=_EXAM_DAY)
            if row.test_definition_id == definition.id and row.employee_id == worker.id
        ]
        self.assertEqual(
            sorted(row.employee_source for row in rows),
            [EMPLOYEE_SOURCE_TEST_EMPLOYEE, EMPLOYEE_SOURCE_THP_WORKER],
        )

    def test_linked_person_keeps_one_validity_row(self) -> None:
        historical_employee = seed_historical_test_employee(
            personal_number=f"h{self.marker}",
            first_name="Jan",
            last_name="Historický",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )
        definition = self._written_test(EXAMINER_MODE_NONE)
        historical = test_exam_service.prepare_exam(
            employee_id=historical_employee.id,
            test_id=definition.id,
            exam_date=_EXAM_DAY,
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        )
        snapshot = (
            historical.employee_source,
            historical.employee_display_name,
            historical.employee_personal_number,
            historical.status,
        )
        worker = self._worker("Jan", "Historický", personal_number=f"c{self.marker}")
        employee_central_link_service.link_existing(
            test_employee_id=historical_employee.id,
            thp_worker_id=worker.id,
        )
        exam_validity_service.stop_tracking(historical_employee.id, definition.id)
        created = test_exam_service.prepare_paper_batch(
            employee_ids=[worker.id],
            test_id=definition.id,
            exam_date=_EXAM_DAY,
        )
        self.assertEqual(created[0].employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(created[0].employee_id, worker.id)
        fresh = test_exam_service.get_exam(historical.id)
        self.assertEqual(
            (
                fresh.employee_source,
                fresh.employee_display_name,
                fresh.employee_personal_number,
                fresh.status,
            ),
            snapshot,
        )
        rows = [
            row
            for row in exam_validity_service.list_rows(today=_EXAM_DAY)
            if row.test_definition_id == definition.id
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(rows[0].employee_id, worker.id)
        self.assertTrue(rows[0].tracked)
        self.assertEqual(rows[0].prepared_count, 2)

    def test_incomplete_or_failed_batch_writes_nothing(self) -> None:
        complete = self._worker("Lea", "Aktivní", personal_number=f"a{self.marker}")
        incomplete = self._worker(
            "Ivo",
            "Mezera",
            personal_number=f"b{self.marker}",
            responsibility_role_ids=[],
        )
        definition = self._written_test(EXAMINER_MODE_NONE)
        before = _count(TestExam)
        with self.assertRaises(TestExamError) as incomplete_error:
            test_exam_service.prepare_paper_batch(
                employee_ids=[complete.id, incomplete.id],
                test_id=definition.id,
                exam_date=_EXAM_DAY,
            )
        self.assertIn("Chybí funkce / role.", str(incomplete_error.exception))
        self.assertIn("Nevytvořila se žádná zkouška.", str(incomplete_error.exception))
        self.assertEqual(_count(TestExam), before)

        other = self._worker("Nela", "Druhá", personal_number=f"c{self.marker}")
        original = TestExamService._insert_prepared_exam
        state = {"n": 0}

        def fail_second(service, *args, **kwargs):
            state["n"] += 1
            if state["n"] == 2:
                raise TestExamError("druhý zápis selhal")
            return original(service, *args, **kwargs)

        with patch.object(TestExamService, "_insert_prepared_exam", fail_second):
            with self.assertRaises(TestExamError) as failed:
                test_exam_service.prepare_paper_batch(
                    employee_ids=[complete.id, other.id],
                    test_id=definition.id,
                    exam_date=_EXAM_DAY,
                )
        self.assertIn("Nevytvořila se žádná zkouška.", str(failed.exception))
        self.assertEqual(_count(TestExam), before)
        self.assertEqual(
            _count(TestExam),
            0,
        )

    def _dialog(self) -> PaperBatchDialog:
        dialog = PaperBatchDialog()
        self.dialogs.append(dialog)
        return dialog

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
            "position": "",
        }
        data.update(extra)
        return settings_service.save_worker(**data)

    def _written_test(self, examiner_mode: str):
        topic = written_question_topic_service.create_topic(name=f"Okruh {self.marker} {examiner_mode}")
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

    def _workplace_index(self, dialog: PaperBatchDialog, name: str) -> int:
        for index in range(dialog.workplace.count()):
            if dialog.workplace.itemText(index) == name:
                return index
        raise AssertionError(name)
