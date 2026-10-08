"""TESTY-12a: evidenční přehled zkoušek a jejich platnosti."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QApplication, QPushButton
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-12a-"))
TODAY = date(2026, 6, 15)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.theme.status_colors import (
        STATUS_DONE_BG,
        STATUS_DONE_TEXT,
        STATUS_IN_PROGRESS_BG,
        STATUS_MISSING_BG,
        STATUS_MISSING_TEXT,
        STATUS_NEUTRAL_BG,
        STATUS_ORANGE_TEXT,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        AGENDA_EXAM_VALIDITY,
        AGENDA_EXAMS,
        EXAM_STATUS_CANCELLED,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_PREPARED,
        EXAM_STATUS_STARTED,
        EXAM_VALIDITY_FILTER_ALL_STATES,
        EXAM_VALIDITY_FILTER_ALL_TESTS,
        EXAM_VALIDITY_FILTER_ALL_WORKPLACES,
        EXAM_VALIDITY_SHOW_INACTIVE,
        EXAM_VALIDITY_STATE_EXPIRED,
        EXAM_VALIDITY_STATE_EXPIRING,
        EXAM_VALIDITY_STATE_LABELS,
        EXAM_VALIDITY_STATE_NO_SUCCESS,
        EXAM_VALIDITY_STATE_UNLIMITED,
        EXAM_VALIDITY_STATE_VALID,
        EXAMINER_MODE_NONE,
        VALIDITY_COL_LAST_SUCCESS,
        VALIDITY_COL_PERSONAL_NUMBER,
        VALIDITY_COL_PREPARED,
        VALIDITY_COL_STATE,
        VALIDITY_COL_VALID_UNTIL,
        VALIDITY_COLUMN_HEADERS,
        VALIDITY_UNIT_YEARS,
        WRITTEN_RESULT_FAILED,
        WRITTEN_RESULT_PASSED,
    )
    from moduly.testy.modely.test_definition import TestDefinition
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.sluzby.exam_validity_service import (
        exam_validity_service,
        filter_exam_validity_rows,
    )
    from moduly.testy.sluzby.test_definition_service import test_definition_service
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import format_exam_date
    from moduly.testy.ui.exam_validity_tab import ExamValidityTab
    from moduly.testy.ui.testy_page import TestyPage


def _wipe() -> None:
    with get_session() as session:
        session.execute(delete(TestExam))
        session.execute(delete(TestDefinition))
        session.execute(delete(TestEmployeeRole))
        session.execute(delete(TestEmployee))
        session.commit()


class ExamValidityOverviewTests(unittest.TestCase):
    def setUp(self) -> None:
        _wipe()
        self.workplace = settings_service.save_workplace(name="Hala Sever")
        self.other_workplace = settings_service.save_workplace(name="Hala Jih")
        self.role = responsibility_role_service.create_role(name="Mistr platnosti")

    def test_employee_without_exam_is_absent(self) -> None:
        self._employee("00100", "Jan", "Novák")
        examined = self._employee("00200", "Eva", "Malá", workplace=self.other_workplace)
        test = self._definition("BOZP")
        self._exam(examined, test, status=EXAM_STATUS_PREPARED, exam_date=TODAY)
        rows = self._rows()
        self.assertEqual([row.personal_number for row in rows], ["00200"])

    def test_prepared_only(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        self._exam(employee, test, status=EXAM_STATUS_PREPARED, exam_date=TODAY)
        self._exam(employee, test, status=EXAM_STATUS_PREPARED, exam_date=TODAY)
        row = self._one()
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_NO_SUCCESS)
        self.assertEqual(row.prepared_count, 2)
        self.assertEqual(row.in_progress_count, 0)
        self.assertIsNone(row.last_success_on)
        self.assertIsNone(row.valid_until)
        self.assertEqual(row.workplace_name, "Hala Sever")
        self.assertEqual(row.test_name, "BOZP")

    def test_in_progress_only(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        self._exam(
            employee,
            test,
            status=EXAM_STATUS_STARTED,
            exam_date=TODAY,
            started_at=datetime(2026, 6, 15, 8, 0),
        )
        row = self._one()
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_NO_SUCCESS)
        self.assertEqual(row.prepared_count, 0)
        self.assertEqual(row.in_progress_count, 1)
        self.assertIsNone(row.last_success_on)
        self.assertIsNone(row.valid_until)

    def test_successful_exam_uses_completion_day_and_current_names(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        exam = self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=date(2020, 1, 1),
            valid_until=date(2027, 3, 1),
            finished_at=datetime(2026, 3, 1, 9, 30),
            result=WRITTEN_RESULT_PASSED,
        )
        row = self._one()
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_VALID)
        self.assertEqual(row.last_success_on, date(2026, 3, 1))
        self.assertEqual(row.valid_until, date(2027, 3, 1))
        self.assertEqual(row.last_success_exam_id, exam.id)
        self.assertEqual(row.employee_name, "Jan Novák")
        self.assertEqual(row.workplace_name, "Hala Sever")
        self.assertEqual(row.test_name, "BOZP")
        self.assertNotEqual(row.workplace_name, "Staré pracoviště")
        self.assertEqual(row.prepared_count, 0)
        self.assertEqual(row.in_progress_count, 0)

    def test_failed_exam(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=date(2026, 6, 1),
            valid_until=date(2027, 6, 1),
            finished_at=datetime(2026, 6, 1, 10, 0),
            result=WRITTEN_RESULT_FAILED,
            written_result=WRITTEN_RESULT_PASSED,
        )
        row = self._one()
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_NO_SUCCESS)
        self.assertIsNone(row.last_success_on)
        self.assertIsNone(row.valid_until)
        self.assertEqual(row.prepared_count, 0)
        self.assertEqual(row.in_progress_count, 0)

    def test_newer_failure_keeps_older_success(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        success = self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=date(2026, 1, 10),
            valid_until=date(2027, 1, 10),
            finished_at=datetime(2026, 1, 10, 9, 0),
            result=WRITTEN_RESULT_PASSED,
        )
        self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=date(2026, 6, 1),
            valid_until=date(2026, 6, 2),
            finished_at=datetime(2026, 6, 1, 9, 0),
            result=WRITTEN_RESULT_FAILED,
            written_result=WRITTEN_RESULT_PASSED,
        )
        row = self._one()
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_VALID)
        self.assertEqual(row.last_success_exam_id, success.id)
        self.assertEqual(row.last_success_on, date(2026, 1, 10))
        self.assertEqual(row.valid_until, date(2027, 1, 10))

    def test_valid_exam_can_have_prepared_exam(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        success = self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=date(2026, 1, 10),
            valid_until=date(2027, 1, 10),
            finished_at=datetime(2026, 1, 10, 9, 0),
            result=WRITTEN_RESULT_PASSED,
        )
        self._exam(employee, test, status=EXAM_STATUS_PREPARED, exam_date=TODAY)
        self._exam(
            employee,
            test,
            status=EXAM_STATUS_STARTED,
            exam_date=TODAY,
            started_at=datetime(2026, 6, 15, 11, 0),
        )
        row = self._one()
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_VALID)
        self.assertEqual(row.last_success_exam_id, success.id)
        self.assertEqual(row.prepared_count, 1)
        self.assertEqual(row.in_progress_count, 1)

    def test_thirty_day_boundary(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        valid_until = date(2026, 7, 15)
        self._passed(employee, test, valid_until=valid_until, finished_on=date(2026, 1, 15))
        ending = self._one(today=date(2026, 6, 15))
        still_valid = self._one(today=date(2026, 6, 14))
        self.assertEqual((valid_until - date(2026, 6, 15)).days, 30)
        self.assertEqual((valid_until - date(2026, 6, 14)).days, 31)
        self.assertEqual(ending.state, EXAM_VALIDITY_STATE_EXPIRING)
        self.assertEqual(still_valid.state, EXAM_VALIDITY_STATE_VALID)

    def test_last_day_of_validity(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        self._passed(employee, test, valid_until=date(2026, 6, 15), finished_on=date(2026, 1, 1))
        row = self._one(today=date(2026, 6, 15))
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_EXPIRING)
        self.assertEqual(row.valid_until, date(2026, 6, 15))

    def test_day_after_validity_ends(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        self._passed(employee, test, valid_until=date(2026, 6, 15), finished_on=date(2026, 1, 1))
        row = self._one(today=date(2026, 6, 16))
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_EXPIRED)

    def test_unlimited_validity(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        exam = self._passed(
            employee,
            test,
            valid_until=date(2027, 1, 1),
            finished_on=date(2026, 1, 1),
        )
        with get_session() as session:
            stored = session.get(TestExam, exam.id)
            stored.valid_until = None
            session.commit()
        row = self._one()
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_UNLIMITED)
        self.assertIsNone(row.valid_until)
        self.assertEqual(row.last_success_on, date(2026, 1, 1))
        self.assertEqual(row.last_success_exam_id, exam.id)

    def test_inactive_employee_hidden_until_requested(self) -> None:
        employee = self._employee("00100", "Jan", "Novák", active=False)
        test = self._definition("BOZP")
        self._passed(employee, test, valid_until=date(2027, 1, 1), finished_on=date(2026, 1, 1))
        self.assertEqual(self._rows(), [])
        shown = self._rows(include_inactive_employees=True)
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0].state, EXAM_VALIDITY_STATE_VALID)
        self.assertFalse(shown[0].employee_active)

    def test_inactive_test_stays_visible_and_keeps_validity(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        self._passed(employee, test, valid_until=date(2027, 1, 1), finished_on=date(2026, 1, 1))
        test_definition_service.deactivate(test.id)
        with get_session() as session:
            stored = session.get(TestDefinition, test.id)
            stored.name = "BOZP historický"
            session.commit()
        row = self._one()
        self.assertFalse(row.test_active)
        self.assertEqual(row.test_name, "BOZP historický")
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_VALID)
        self.assertEqual(row.valid_until, date(2027, 1, 1))

    def test_cancelled_exam_does_not_create_row(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        other = self._employee("00200", "Eva", "Malá", workplace=self.other_workplace)
        test = self._definition("BOZP")
        self._exam(employee, test, status=EXAM_STATUS_CANCELLED, exam_date=TODAY)
        self.assertEqual(self._rows(), [])
        success = self._passed(
            other,
            test,
            valid_until=date(2027, 1, 1),
            finished_on=date(2026, 1, 1),
        )
        self._exam(other, test, status=EXAM_STATUS_CANCELLED, exam_date=TODAY)
        row = self._one()
        self.assertEqual(row.personal_number, "00200")
        self.assertEqual(row.last_success_exam_id, success.id)
        self.assertEqual(row.prepared_count, 0)
        self.assertEqual(row.in_progress_count, 0)
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_VALID)

    def test_latest_completion_date_then_higher_id(self) -> None:
        same_day = self._employee("00100", "Jan", "Novák")
        later_day = self._employee("00200", "Eva", "Malá", workplace=self.other_workplace)
        test = self._definition("BOZP")
        self._exam(
            same_day,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=date(2026, 3, 1),
            valid_until=date(2027, 3, 1),
            finished_at=datetime(2026, 3, 1, 18, 0),
            result=WRITTEN_RESULT_PASSED,
        )
        newer_id = self._exam(
            same_day,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=date(2026, 3, 1),
            valid_until=date(2028, 1, 1),
            finished_at=datetime(2026, 3, 1, 8, 0),
            result=WRITTEN_RESULT_PASSED,
        )
        later_date = self._exam(
            later_day,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=date(2026, 5, 1),
            valid_until=date(2027, 5, 1),
            finished_at=datetime(2026, 5, 1, 8, 0),
            result=WRITTEN_RESULT_PASSED,
        )
        self._exam(
            later_day,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=date(2026, 1, 1),
            valid_until=date(2029, 1, 1),
            finished_at=datetime(2026, 1, 1, 8, 0),
            result=WRITTEN_RESULT_PASSED,
        )
        rows = {row.personal_number: row for row in self._rows()}
        self.assertEqual(rows["00100"].last_success_exam_id, newer_id.id)
        self.assertEqual(rows["00100"].valid_until, date(2028, 1, 1))
        self.assertEqual(rows["00100"].last_success_on, date(2026, 3, 1))
        self.assertEqual(rows["00200"].last_success_exam_id, later_date.id)
        self.assertEqual(rows["00200"].valid_until, date(2027, 5, 1))

    def test_filters_search_workplace_test_and_state(self) -> None:
        jan = self._employee("00100", "Jan", "Novák")
        eva = self._employee("00200", "Eva", "Malá", workplace=self.other_workplace)
        bozp = self._definition("BOZP")
        crane = self._definition("Jeřáby")
        self._passed(jan, bozp, valid_until=date(2027, 1, 1), finished_on=date(2026, 1, 1))
        self._exam(eva, crane, status=EXAM_STATUS_PREPARED, exam_date=TODAY)
        rows = self._rows()
        self.assertEqual(
            [row.personal_number for row in self._filtered(rows, search="00100")],
            ["00100"],
        )
        self.assertEqual(
            [row.personal_number for row in self._filtered(rows, search="malá")],
            ["00200"],
        )
        self.assertEqual(
            [row.personal_number for row in self._filtered(rows, search="jeřáb")],
            ["00200"],
        )
        self.assertEqual(self._filtered(rows, search="Hala"), [])
        self.assertEqual(
            [row.personal_number for row in self._filtered(rows, workplace_id=self.workplace.id)],
            ["00100"],
        )
        self.assertEqual(
            [row.personal_number for row in self._filtered(rows, test_definition_id=crane.id)],
            ["00200"],
        )
        self.assertEqual(
            [row.state for row in self._filtered(rows, state=EXAM_VALIDITY_STATE_VALID)],
            [EXAM_VALIDITY_STATE_VALID],
        )
        self.assertEqual(
            [row.state for row in self._filtered(rows, state=EXAM_VALIDITY_STATE_NO_SUCCESS)],
            [EXAM_VALIDITY_STATE_NO_SUCCESS],
        )

    def test_default_clock_is_local_today(self) -> None:
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        local_today = date.today()
        self._passed(
            employee,
            test,
            valid_until=local_today + timedelta(days=31),
            finished_on=local_today,
        )
        self.assertEqual(self._one(today=None).state, EXAM_VALIDITY_STATE_VALID)
        self._wipe_exams()
        self._passed(
            employee,
            test,
            valid_until=local_today + timedelta(days=30),
            finished_on=local_today,
        )
        self.assertEqual(self._one(today=None).state, EXAM_VALIDITY_STATE_EXPIRING)
        self._wipe_exams()
        self._passed(
            employee,
            test,
            valid_until=local_today,
            finished_on=local_today,
        )
        self.assertEqual(self._one(today=None).state, EXAM_VALIDITY_STATE_EXPIRING)
        self._wipe_exams()
        self._passed(
            employee,
            test,
            valid_until=local_today - timedelta(days=1),
            finished_on=local_today - timedelta(days=10),
        )
        self.assertEqual(self._one(today=None).state, EXAM_VALIDITY_STATE_EXPIRED)

    def _wipe_exams(self) -> None:
        with get_session() as session:
            session.execute(delete(TestExam))
            session.commit()

    def _rows(self, **kwargs):
        today = kwargs.pop("today", TODAY)
        include_inactive_employees = kwargs.pop("include_inactive_employees", False)
        if today is None:
            listed = exam_validity_service.list_rows(
                include_inactive_employees=include_inactive_employees,
            )
        else:
            listed = exam_validity_service.list_rows(
                today=today,
                include_inactive_employees=include_inactive_employees,
            )
        return filter_exam_validity_rows(listed, **kwargs)

    def _filtered(self, rows, **kwargs):
        return filter_exam_validity_rows(rows, **kwargs)

    def _one(self, **kwargs):
        rows = self._rows(**kwargs)
        self.assertEqual(len(rows), 1)
        return rows[0]

    def _employee(self, number, first, last, *, workplace=None, active=True):
        return test_employee_service.create_employee(
            personal_number=number,
            first_name=first,
            last_name=last,
            workplace_id=(workplace or self.workplace).id,
            responsibility_role_ids=[self.role.id],
            active=active,
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

    def _passed(self, employee, test, *, valid_until: date, finished_on: date) -> TestExam:
        return self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=finished_on,
            valid_until=valid_until,
            finished_at=datetime(finished_on.year, finished_on.month, finished_on.day, 9, 0),
            result=WRITTEN_RESULT_PASSED,
        )

    def _exam(
        self,
        employee,
        test,
        *,
        status: str,
        exam_date: date,
        valid_until: date | None = None,
        finished_at: datetime | None = None,
        started_at: datetime | None = None,
        result: str | None = None,
        written_result: str | None = None,
    ) -> TestExam:
        if valid_until is None and status == EXAM_STATUS_COMPLETED and result == WRITTEN_RESULT_PASSED:
            valid_until = date(2027, 1, 1)
        exam = TestExam(
            employee_id=employee.id,
            test_definition_id=test.id,
            exam_date=exam_date,
            valid_until=valid_until if valid_until is not None else exam_date,
            status=status,
            examiner_mode=EXAMINER_MODE_NONE,
            employee_personal_number=employee.personal_number,
            employee_first_name=employee.first_name,
            employee_last_name=employee.last_name,
            employee_display_name=employee.display_name,
            employee_workplace_name="Staré pracoviště",
            test_name="Starý název testu",
            uses_written=False,
            uses_oral=False,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            written_duration_seconds=0,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_finish_reason="",
            written_started_at=started_at,
            written_finished_at=finished_at,
            written_result=written_result,
            exam_result=result,
        )
        with get_session() as session:
            session.add(exam)
            session.commit()
            session.refresh(exam)
            session.expunge(exam)
        return exam


class ExamValidityTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _wipe()
        self.workplace = settings_service.save_workplace(name="Hala Sever")
        self.other_workplace = settings_service.save_workplace(name="Hala Jih")
        self.role = responsibility_role_service.create_role(name="Mistr záložky")

    def test_tab_follows_exams_and_is_read_only(self) -> None:
        page = TestyPage()
        labels = [page.tabs.tabText(index) for index in range(page.tabs.count())]
        self.assertEqual(labels[labels.index(AGENDA_EXAMS) + 1], AGENDA_EXAM_VALIDITY)
        tab = page.validity_tab
        self.assertFalse(tab.show_inactive.isChecked())
        self.assertEqual(tab.show_inactive.text(), EXAM_VALIDITY_SHOW_INACTIVE)
        self.assertEqual(tab.workplace_filter.currentText(), EXAM_VALIDITY_FILTER_ALL_WORKPLACES)
        self.assertEqual(tab.test_filter.currentText(), EXAM_VALIDITY_FILTER_ALL_TESTS)
        self.assertEqual(tab.state_filter.currentText(), EXAM_VALIDITY_FILTER_ALL_STATES)
        self.assertIsNone(tab.workplace_filter.currentData())
        self.assertIsNone(tab.test_filter.currentData())
        self.assertIsNone(tab.state_filter.currentData())
        self.assertEqual(tab.findChildren(QPushButton), [])
        self.assertEqual(
            tab.table.editTriggers(),
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        headers = [
            tab.table.horizontalHeaderItem(column).text()
            for column in range(tab.table.columnCount())
        ]
        self.assertEqual(headers, list(VALIDITY_COLUMN_HEADERS))
        page.deleteLater()

    def test_table_shows_state_colors_and_filters(self) -> None:
        jan = self._employee("00100", "Jan", "Novák")
        eva = self._employee("00200", "Eva", "Malá", workplace=self.other_workplace)
        bozp = self._definition("BOZP")
        crane = self._definition("Jeřáby")
        self._passed(jan, bozp, valid_until=date(2027, 1, 10), finished_on=date(2026, 1, 10))
        self._passed(eva, crane, valid_until=TODAY, finished_on=date(2026, 1, 1))
        expired = self._employee("00300", "Petr", "Svoboda")
        self._passed(expired, bozp, valid_until=date(2026, 6, 14), finished_on=date(2026, 1, 1))
        unlimited = self._employee("00400", "Iva", "Dvořáková", workplace=self.other_workplace)
        open_ended = self._passed(
            unlimited,
            crane,
            valid_until=date(2027, 1, 1),
            finished_on=date(2026, 2, 2),
        )
        with get_session() as session:
            stored = session.get(TestExam, open_ended.id)
            stored.valid_until = None
            session.commit()
        pending = self._employee("00500", "Adam", "Černý")
        self._exam(pending, bozp, status=EXAM_STATUS_PREPARED, exam_date=TODAY)

        tab = ExamValidityTab()
        tab.today_override = TODAY
        tab.refresh()
        self.assertEqual(tab.table.rowCount(), 5)
        self._assert_state("00100", tab, EXAM_VALIDITY_STATE_VALID, STATUS_DONE_BG, STATUS_DONE_TEXT)
        self._assert_state(
            "00200",
            tab,
            EXAM_VALIDITY_STATE_EXPIRING,
            STATUS_IN_PROGRESS_BG,
            STATUS_ORANGE_TEXT,
        )
        self._assert_state(
            "00300",
            tab,
            EXAM_VALIDITY_STATE_EXPIRED,
            STATUS_MISSING_BG,
            STATUS_MISSING_TEXT,
        )
        self._assert_state("00400", tab, EXAM_VALIDITY_STATE_UNLIMITED, STATUS_NEUTRAL_BG, None)
        self._assert_state("00500", tab, EXAM_VALIDITY_STATE_NO_SUCCESS, STATUS_NEUTRAL_BG, None)
        success_row = self._row(tab, "00100")
        self.assertEqual(
            tab.table.item(success_row, VALIDITY_COL_LAST_SUCCESS).text(),
            format_exam_date(date(2026, 1, 10)),
        )
        self.assertEqual(
            tab.table.item(success_row, VALIDITY_COL_VALID_UNTIL).text(),
            format_exam_date(date(2027, 1, 10)),
        )
        self.assertEqual(tab.table.item(success_row, VALIDITY_COL_PREPARED).text(), "0")
        self.assertEqual(tab.table.item(self._row(tab, "00500"), VALIDITY_COL_PREPARED).text(), "1")
        self.assertEqual(tab.table.item(self._row(tab, "00400"), VALIDITY_COL_VALID_UNTIL).text(), "")

        tab.text_filter.search_edit.setText("malá")
        self.assertFalse(tab.table.isRowHidden(self._row(tab, "00200")))
        self.assertTrue(tab.table.isRowHidden(self._row(tab, "00100")))
        tab.text_filter.search_edit.clear()

        workplace_index = tab.workplace_filter.findData(self.other_workplace.id)
        tab.workplace_filter.setCurrentIndex(workplace_index)
        self.assertCountEqual(self._visible_numbers(tab), ["00200", "00400"])
        tab.workplace_filter.setCurrentIndex(0)

        test_index = tab.test_filter.findData(crane.id)
        tab.test_filter.setCurrentIndex(test_index)
        self.assertCountEqual(self._visible_numbers(tab), ["00200", "00400"])
        inactive_label = tab.test_filter.itemText(test_index)
        self.assertNotIn("(neaktivní)", inactive_label)
        tab.test_filter.setCurrentIndex(0)

        state_index = tab.state_filter.findData(EXAM_VALIDITY_STATE_EXPIRED)
        tab.state_filter.setCurrentIndex(state_index)
        self.assertEqual(self._visible_numbers(tab), ["00300"])
        tab.deleteLater()

    def test_overview_reloads_after_exam_change_and_reopen(self) -> None:
        page = TestyPage()
        page.validity_tab.today_override = TODAY
        page.tabs.setCurrentWidget(page.validity_tab)
        self.assertEqual(page.validity_tab.table.rowCount(), 0)
        employee = self._employee("00100", "Jan", "Novák")
        test = self._definition("BOZP")
        page.tabs.setCurrentWidget(page.exams_tab)
        self._exam(employee, test, status=EXAM_STATUS_PREPARED, exam_date=TODAY)
        page.tabs.setCurrentWidget(page.validity_tab)
        self.assertEqual(page.validity_tab.table.rowCount(), 1)
        self.assertEqual(
            page.validity_tab.table.item(0, VALIDITY_COL_PERSONAL_NUMBER).text(),
            "00100",
        )
        self._exam(employee, test, status=EXAM_STATUS_PREPARED, exam_date=TODAY)
        page.exams_tab.refresh()
        prepared = page.validity_tab.table.item(0, VALIDITY_COL_PREPARED).text()
        self.assertEqual(prepared, "2")
        page.tabs.setCurrentWidget(page.employees_tab)
        self._exam(employee, test, status=EXAM_STATUS_PREPARED, exam_date=TODAY)
        page.refresh()
        page.tabs.setCurrentWidget(page.validity_tab)
        self.assertEqual(
            page.validity_tab.table.item(0, VALIDITY_COL_PREPARED).text(),
            "3",
        )
        page.deleteLater()

    def _assert_state(self, number, tab, state, background, foreground) -> None:
        row = self._row(tab, number)
        item = tab.table.item(row, VALIDITY_COL_STATE)
        self.assertEqual(item.text(), EXAM_VALIDITY_STATE_LABELS[state])
        self.assertEqual(item.background().color().name(), QColor(background).name())
        if foreground is not None:
            self.assertEqual(item.foreground().color().name(), QColor(foreground).name())

    def _row(self, tab, number: str) -> int:
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, VALIDITY_COL_PERSONAL_NUMBER)
            if item is not None and item.text() == number:
                return row
        self.fail(f"Řádek {number} není v přehledu.")
        return -1

    def _visible_numbers(self, tab) -> list[str]:
        numbers = []
        for row in range(tab.table.rowCount()):
            if tab.table.isRowHidden(row):
                continue
            item = tab.table.item(row, VALIDITY_COL_PERSONAL_NUMBER)
            numbers.append(item.text() if item is not None else "")
        return numbers

    def _employee(self, number, first, last, *, workplace=None):
        return test_employee_service.create_employee(
            personal_number=number,
            first_name=first,
            last_name=last,
            workplace_id=(workplace or self.workplace).id,
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

    def _passed(self, employee, test, *, valid_until: date, finished_on: date) -> TestExam:
        return self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            exam_date=finished_on,
            valid_until=valid_until,
            finished_at=datetime(finished_on.year, finished_on.month, finished_on.day, 9, 0),
            result=WRITTEN_RESULT_PASSED,
        )

    def _exam(self, employee, test, *, status, exam_date, valid_until=None, finished_at=None, result=None):
        exam = TestExam(
            employee_id=employee.id,
            test_definition_id=test.id,
            exam_date=exam_date,
            valid_until=valid_until if valid_until is not None else exam_date,
            status=status,
            examiner_mode=EXAMINER_MODE_NONE,
            employee_personal_number=employee.personal_number,
            employee_first_name=employee.first_name,
            employee_last_name=employee.last_name,
            employee_display_name=employee.display_name,
            employee_workplace_name="Staré pracoviště",
            test_name="Starý název testu",
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
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
