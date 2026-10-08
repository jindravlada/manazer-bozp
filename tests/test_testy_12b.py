"""TESTY-12b: vypnutí a obnovení sledování platnosti."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import delete, func, select, text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-12b-"))
TODAY = date(2026, 6, 15)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _db_engine,
        _ensure_test_exam_tables,
        _table_exists,
        initialize_database,
    )

    initialize_database()

    from core.database.session import get_session
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_TEXT,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_PREPARED,
        EXAM_STATUS_STARTED,
        EXAM_VALIDITY_ACTION_RESUME,
        EXAM_VALIDITY_ACTION_STOP,
        EXAM_VALIDITY_TRACKING_FILTER_ALL,
        EXAM_VALIDITY_TRACKING_FILTER_TRACKED,
        EXAM_VALIDITY_TRACKING_FILTER_TRACKED_LABEL,
        EXAM_VALIDITY_TRACKING_FILTER_UNTRACKED,
        EXAM_VALIDITY_TRACKING_OFF_LABEL,
        EXAM_VALIDITY_TRACKING_ON_LABEL,
        EXAMINER_MODE_NONE,
        VALIDITY_COL_IN_PROGRESS,
        VALIDITY_COL_PERSONAL_NUMBER,
        VALIDITY_COL_PREPARED,
        VALIDITY_COL_TRACKING,
        VALIDITY_UNIT_YEARS,
        WRITTEN_RESULT_PASSED,
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
    from moduly.testy.sluzby.exam_validity_service import (
        exam_validity_service,
        filter_exam_validity_rows,
        unfinished_exam_counts,
        validity_rows_for_summary,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.exam_validity_tab import ExamValidityTab


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
        session.execute(delete(TestEmployeeRole))
        session.execute(delete(TestEmployee))
        session.commit()


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


class ExamValidityTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        _wipe()
        self.workplace = settings_service.save_workplace(name="Hala Sever")
        self.role = responsibility_role_service.create_role(name="Mistr sledování")

    def test_existing_combination_is_tracked_by_default(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        self._exam(employee, test, status=EXAM_STATUS_PREPARED)
        row = self._one()
        self.assertTrue(row.tracked)
        self.assertEqual(self._tracking_count(), 0)

    def test_stop_and_manual_resume_keep_history(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        other = self._employee("00200", "Eva", "Malá")
        test = self._definition("BOZP")
        exam = self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            valid_until=date(2027, 1, 10),
            finished_at=datetime(2026, 1, 10, 9, 0),
            result=WRITTEN_RESULT_PASSED,
        )
        self._exam(employee, test, status=EXAM_STATUS_PREPARED)
        self._exam(
            employee,
            test,
            status=EXAM_STATUS_STARTED,
            started_at=datetime(2026, 6, 15, 8, 0),
        )
        self._exam(other, test, status=EXAM_STATUS_PREPARED)
        before = self._signature(exam.id)
        original_state = self._one_for(employee.id).state
        exam_count = self._exam_count()

        exam_validity_service.stop_tracking(employee.id, test.id)
        exam_validity_service.stop_tracking(employee.id, test.id)
        stopped = self._one_for(employee.id)
        self.assertFalse(stopped.tracked)
        self.assertEqual(stopped.state, original_state)
        self.assertEqual(stopped.prepared_count, 1)
        self.assertEqual(stopped.in_progress_count, 1)
        self.assertEqual(stopped.valid_until, date(2027, 1, 10))
        self.assertEqual(self._signature(exam.id), before)
        self.assertEqual(self._exam_count(), exam_count)
        self.assertEqual(self._tracking_count(), 1)
        self.assertTrue(self._one_for(other.id).tracked)

        rows = exam_validity_service.list_rows(today=TODAY)
        self.assertEqual(
            [row.personal_number for row in filter_exam_validity_rows(
                rows,
                tracking=EXAM_VALIDITY_TRACKING_FILTER_TRACKED,
            )],
            ["00200"],
        )
        self.assertEqual(
            [row.personal_number for row in filter_exam_validity_rows(
                rows,
                tracking=EXAM_VALIDITY_TRACKING_FILTER_UNTRACKED,
            )],
            ["00100"],
        )
        self.assertEqual(len(filter_exam_validity_rows(rows, tracking=None)), 2)
        self.assertEqual(
            [row.personal_number for row in validity_rows_for_summary(rows)],
            ["00200"],
        )
        self.assertEqual(unfinished_exam_counts(rows), (2, 1))

        exam_validity_service.resume_tracking(employee.id, test.id)
        restored = self._one_for(employee.id)
        self.assertTrue(restored.tracked)
        self.assertEqual(restored.prepared_count, 1)
        self.assertEqual(restored.in_progress_count, 1)
        self.assertEqual(restored.valid_until, date(2027, 1, 10))
        self.assertEqual(self._signature(exam.id), before)
        self.assertEqual(self._exam_count(), exam_count)
        self.assertEqual(self._tracking_count(), 0)

    def test_individual_prepare_restores_only_that_pair(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        other = self._employee("00200", "Eva", "Malá")
        test = self._written_definition("BOZP")
        first = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=test.id,
            exam_date=date(2026, 1, 10),
            rng=PrefixReverse(),
        )
        test_exam_service.prepare_exam(
            employee_id=other.id,
            test_id=test.id,
            exam_date=date(2026, 1, 10),
            rng=PrefixReverse(),
        )
        before = self._signature(first.id)
        exam_validity_service.stop_tracking(employee.id, test.id)
        exam_validity_service.stop_tracking(other.id, test.id)
        created = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=test.id,
            exam_date=TODAY,
            rng=PrefixReverse(),
        )
        self.assertNotEqual(created.id, first.id)
        self.assertTrue(self._one_for(employee.id).tracked)
        self.assertFalse(self._one_for(other.id).tracked)
        self.assertEqual(self._signature(first.id), before)
        self.assertEqual(self._exam_count(), 3)

    def test_paper_batch_restores_only_prepared_employees(self) -> None:
        first = self._employee("00100", "Jan", "Novák")
        second = self._employee("00200", "Eva", "Malá")
        outside = self._employee("00300", "Petr", "Svoboda")
        test = self._written_definition("BOZP")
        for employee in (first, second, outside):
            self._exam(employee, test, status=EXAM_STATUS_PREPARED)
            exam_validity_service.stop_tracking(employee.id, test.id)
        created = test_exam_service.prepare_paper_batch(
            employee_ids=[first.id, second.id],
            test_id=test.id,
            exam_date=TODAY,
            rng=PrefixReverse(),
        )
        self.assertEqual(len(created), 2)
        self.assertTrue(self._one_for(first.id).tracked)
        self.assertTrue(self._one_for(second.id).tracked)
        self.assertFalse(self._one_for(outside.id).tracked)
        self.assertEqual(self._one_for(outside.id).prepared_count, 1)

    def test_opening_or_editing_exam_does_not_restore(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        exam = self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            valid_until=date(2027, 6, 1),
            finished_at=datetime(2026, 1, 1, 9, 0),
            result=WRITTEN_RESULT_PASSED,
        )
        exam_validity_service.stop_tracking(employee.id, test.id)
        opened = test_exam_service.get_exam(exam.id)
        self.assertEqual(opened.id, exam.id)
        self.assertFalse(self._one_for(employee.id).tracked)
        with get_session() as session:
            stored = session.get(TestExam, exam.id)
            stored.employee_roles_text = "upraveno při otevření"
            session.commit()
        self.assertEqual(
            test_exam_service.get_exam(exam.id).employee_roles_text,
            "upraveno při otevření",
        )
        self.assertFalse(self._one_for(employee.id).tracked)
        self.assertEqual(self._signature(exam.id)[:4], (
            EXAM_STATUS_COMPLETED,
            WRITTEN_RESULT_PASSED,
            date(2027, 6, 1),
            datetime(2026, 1, 1, 9, 0),
        ))
        with self.assertRaises(TestExamError):
            test_exam_service.prepare_exam(
                employee_id=employee.id,
                test_id=test.id,
                exam_date=TODAY,
                valid_until=date(2026, 1, 1),
            )
        self.assertFalse(self._one_for(employee.id).tracked)
        self.assertEqual(self._exam_count(), 1)

    def test_existing_database_receives_tracking_table(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        exam = self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            valid_until=date(2027, 1, 1),
            finished_at=datetime(2026, 1, 1, 9, 0),
            result=WRITTEN_RESULT_PASSED,
        )
        with _db_engine().connect() as connection:
            connection.execute(text("DROP TABLE test_exam_validity_tracking"))
            connection.commit()
        self.assertFalse(_table_exists("test_exam_validity_tracking"))
        _ensure_test_exam_tables()
        self.assertTrue(_table_exists("test_exam_validity_tracking"))
        loaded = test_exam_service.get_exam(exam.id)
        self.assertEqual(loaded.valid_until, date(2027, 1, 1))
        self.assertEqual(loaded.exam_result, WRITTEN_RESULT_PASSED)
        self.assertTrue(self._one_for(employee.id).tracked)

    def _one(self):
        rows = exam_validity_service.list_rows(today=TODAY)
        self.assertEqual(len(rows), 1)
        return rows[0]

    def _one_for(self, employee_id: int):
        rows = [
            row
            for row in exam_validity_service.list_rows(today=TODAY)
            if row.employee_id == employee_id
        ]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def _signature(self, exam_id: int):
        exam = test_exam_service.get_exam(exam_id)
        return (
            exam.status,
            exam.exam_result,
            exam.valid_until,
            exam.written_finished_at,
            exam.exam_date,
        )

    def _exam_count(self) -> int:
        with get_session() as session:
            return int(session.scalar(select(func.count()).select_from(TestExam)) or 0)

    def _tracking_count(self) -> int:
        with get_session() as session:
            return int(
                session.scalar(select(func.count()).select_from(TestExamValidityTracking)) or 0
            )

    def _employee(self, number, first, last):
        return test_employee_service.create_employee(
            personal_number=number,
            first_name=first,
            last_name=last,
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )

    def _definition(self, name: str) -> TestDefinition:
        test = TestDefinition(
            name=name,
            description="",
            active=True,
            uses_written=False,
            uses_oral=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
        )
        with get_session() as session:
            session.add(test)
            session.commit()
            session.refresh(test)
            session.expunge(test)
        return test

    def _written_definition(self, name: str):
        topic = written_question_topic_service.create_topic(name=f"Okruh {name}")
        written_question_service.create_question(
            topic_id=topic.id,
            text=f"Otázka {name}",
            answer_kind=ANSWER_KIND_TEXT,
            answers=[
                WrittenAnswerInput(text="první", is_correct=True),
                WrittenAnswerInput(text="druhá"),
                WrittenAnswerInput(text="třetí"),
            ],
        )
        return test_definition_service.create_test(
            name=name,
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )

    def _exam(
        self,
        employee,
        test,
        *,
        status: str,
        valid_until: date | None = None,
        finished_at: datetime | None = None,
        started_at: datetime | None = None,
        result: str | None = None,
    ) -> TestExam:
        exam_day = finished_at.date() if finished_at is not None else TODAY
        exam = TestExam(
            employee_id=employee.id,
            test_definition_id=test.id,
            exam_date=exam_day,
            valid_until=valid_until if valid_until is not None else exam_day,
            status=status,
            examiner_mode=EXAMINER_MODE_NONE,
            employee_personal_number=employee.personal_number,
            employee_first_name=employee.first_name,
            employee_last_name=employee.last_name,
            employee_display_name=employee.display_name,
            employee_workplace_name=self.workplace.name,
            test_name=test.name,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_started_at=started_at,
            written_finished_at=finished_at,
            exam_result=result,
        )
        with get_session() as session:
            session.add(exam)
            session.commit()
            session.refresh(exam)
            session.expunge(exam)
        return exam


class ExamValidityTrackingTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _wipe()
        self.workplace = settings_service.save_workplace(name="Hala Jih")
        self.role = responsibility_role_service.create_role(name="Mistr záložky sledování")
        self.jan = self._employee("00100", "Jan", "Novák")
        self.eva = self._employee("00200", "Eva", "Malá")
        self.test = self._definition("BOZP")
        self._exam(self.jan, status=EXAM_STATUS_PREPARED)
        self._exam(self.jan, status=EXAM_STATUS_STARTED, started_at=datetime(2026, 6, 15, 8, 0))
        self._exam(
            self.eva,
            status=EXAM_STATUS_COMPLETED,
            valid_until=date(2027, 1, 1),
            finished_at=datetime(2026, 1, 1, 9, 0),
            result=WRITTEN_RESULT_PASSED,
        )

    def test_buttons_confirmation_and_tracking_filter(self) -> None:
        tab = ExamValidityTab()
        tab.today_override = TODAY
        tab.refresh()
        self.assertEqual(tab.stop_btn.text(), EXAM_VALIDITY_ACTION_STOP)
        self.assertEqual(tab.resume_btn.text(), EXAM_VALIDITY_ACTION_RESUME)
        self.assertEqual(
            tab.tracking_filter.currentText(),
            EXAM_VALIDITY_TRACKING_FILTER_TRACKED_LABEL,
        )
        self.assertEqual(tab.tracking_filter.currentData(), EXAM_VALIDITY_TRACKING_FILTER_TRACKED)
        self.assertFalse(tab.stop_btn.isEnabled())
        self.assertFalse(tab.resume_btn.isEnabled())
        self.assertCountEqual(self._numbers(tab), ["00100", "00200"])
        self.assertEqual(
            tab.table.item(self._row(tab, "00100"), VALIDITY_COL_TRACKING).text(),
            EXAM_VALIDITY_TRACKING_ON_LABEL,
        )

        self._select(tab, "00100")
        self.assertTrue(tab.stop_btn.isEnabled())
        self.assertFalse(tab.resume_btn.isEnabled())
        self._select_both(tab)
        self.assertFalse(tab.stop_btn.isEnabled())
        self.assertFalse(tab.resume_btn.isEnabled())

        self._select(tab, "00100")
        with patch(
            "moduly.testy.ui.exam_validity_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            tab.stop_btn.click()
        self.assertCountEqual(self._numbers(tab), ["00100", "00200"])
        self.assertEqual(
            tab.table.item(self._row(tab, "00100"), VALIDITY_COL_TRACKING).text(),
            EXAM_VALIDITY_TRACKING_ON_LABEL,
        )

        self._select(tab, "00100")
        with patch(
            "moduly.testy.ui.exam_validity_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            tab.stop_btn.click()
        self.assertEqual(self._numbers(tab), ["00200"])
        untracked_index = tab.tracking_filter.findData(EXAM_VALIDITY_TRACKING_FILTER_UNTRACKED)
        tab.tracking_filter.setCurrentIndex(untracked_index)
        self.assertEqual(self._numbers(tab), ["00100"])
        row = self._row(tab, "00100")
        self.assertEqual(
            tab.table.item(row, VALIDITY_COL_TRACKING).text(),
            EXAM_VALIDITY_TRACKING_OFF_LABEL,
        )
        self.assertEqual(tab.table.item(row, VALIDITY_COL_PREPARED).text(), "1")
        self.assertEqual(tab.table.item(row, VALIDITY_COL_IN_PROGRESS).text(), "1")
        self._select(tab, "00100")
        self.assertFalse(tab.stop_btn.isEnabled())
        self.assertTrue(tab.resume_btn.isEnabled())

        tab.resume_btn.click()
        self.assertEqual(self._numbers(tab), [])
        all_index = tab.tracking_filter.findData(EXAM_VALIDITY_TRACKING_FILTER_ALL)
        tab.tracking_filter.setCurrentIndex(all_index)
        self.assertCountEqual(self._numbers(tab), ["00100", "00200"])
        self.assertEqual(
            tab.table.item(self._row(tab, "00100"), VALIDITY_COL_TRACKING).text(),
            EXAM_VALIDITY_TRACKING_ON_LABEL,
        )
        tab.deleteLater()

    def _numbers(self, tab) -> list[str]:
        numbers = []
        for row in range(tab.table.rowCount()):
            if tab.table.isRowHidden(row):
                continue
            item = tab.table.item(row, VALIDITY_COL_PERSONAL_NUMBER)
            numbers.append(item.text() if item is not None else "")
        return numbers

    def _row(self, tab, number: str) -> int:
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, VALIDITY_COL_PERSONAL_NUMBER)
            if item is not None and item.text() == number:
                return row
        self.fail(number)
        return -1

    def _select(self, tab, number: str) -> None:
        tab.table.selectRow(self._row(tab, number))

    def _select_both(self, tab) -> None:
        tab.table.clearSelection()
        tab.table.selectRow(0)
        flags = (
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
        )
        tab.table.selectionModel().select(tab.table.model().index(1, 0), flags)

    def _employee(self, number, first, last):
        return test_employee_service.create_employee(
            personal_number=number,
            first_name=first,
            last_name=last,
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )

    def _definition(self, name: str) -> TestDefinition:
        test = TestDefinition(
            name=name,
            description="",
            active=True,
            uses_written=False,
            uses_oral=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
        )
        with get_session() as session:
            session.add(test)
            session.commit()
            session.refresh(test)
            session.expunge(test)
        return test

    def _exam(self, employee, *, status, valid_until=None, finished_at=None, started_at=None, result=None):
        exam_day = finished_at.date() if finished_at is not None else TODAY
        exam = TestExam(
            employee_id=employee.id,
            test_definition_id=self.test.id,
            exam_date=exam_day,
            valid_until=valid_until if valid_until is not None else exam_day,
            status=status,
            examiner_mode=EXAMINER_MODE_NONE,
            employee_personal_number=employee.personal_number,
            employee_first_name=employee.first_name,
            employee_last_name=employee.last_name,
            employee_display_name=employee.display_name,
            employee_workplace_name=self.workplace.name,
            test_name=self.test.name,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_started_at=started_at,
            written_finished_at=finished_at,
            exam_result=result,
        )
        with get_session() as session:
            session.add(exam)
            session.commit()
            session.refresh(exam)
            session.expunge(exam)
        return exam


if __name__ == "__main__":
    unittest.main()
