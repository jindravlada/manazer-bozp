"""EMPLOYEE-CENTRAL-8: společná platnost propojeného zaměstnance."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-8-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database
    from core.database.session import get_session

    initialize_database()

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
        EXAM_STATUS_COMPLETED,
        EXAM_VALIDITY_STATE_EXPIRED,
        EXAM_VALIDITY_STATE_VALID,
        EXAMINER_MODE_SINGLE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_MODE_ELECTRONIC,
        WRITTEN_RESULT_PASSED,
    )
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.sluzby.exam_protocol_export_service import (
        exam_protocol_export_service,
    )
    from moduly.testy.sluzby.exam_validity_service import (
        exam_retraining_summary,
        exam_validity_service,
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


def _db_path() -> Path:
    return Path(storage_module.storage_service.database_path)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(_db_path()))
    connection.row_factory = sqlite3.Row
    return connection


def _tracking_rows() -> list[sqlite3.Row]:
    connection = _connect()
    try:
        return list(
            connection.execute(
                """
                SELECT employee_source, employee_id, test_definition_id
                FROM test_exam_validity_tracking
                ORDER BY employee_source, employee_id, test_definition_id
                """
            )
        )
    finally:
        connection.close()


def _complete_exam(exam_id: int, *, finished: datetime, valid_until: date) -> None:
    connection = _connect()
    try:
        connection.execute(
            """
            UPDATE test_exams
            SET status = ?, exam_result = ?, written_result = ?, written_mode = ?,
                written_finished_at = ?, valid_until = ?,
                written_question_count = 2, written_correct_count = 2,
                written_incorrect_count = 0, written_unanswered_count = 0,
                written_allowed_wrong_answers = 0
            WHERE id = ?
            """,
            (
                EXAM_STATUS_COMPLETED,
                WRITTEN_RESULT_PASSED,
                WRITTEN_RESULT_PASSED,
                WRITTEN_MODE_ELECTRONIC,
                finished.isoformat(sep=" "),
                valid_until.isoformat(),
                exam_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _clone_exam(source_id: int, *, employee_id: int, employee_source: str, **overrides):
    source = test_exam_service.get_exam(source_id)
    assert source is not None
    values = {
        column.name: getattr(source, column.name)
        for column in TestExam.__table__.columns
        if column.name not in {"id", "created_at"}
    }
    values["employee_id"] = employee_id
    values["employee_source"] = employee_source
    values.update(overrides)
    with get_session() as session:
        row = TestExam(**values)
        session.add(row)
        session.commit()
        new_id = int(row.id)
    return new_id


def _snapshot_fields(exam_id: int) -> dict:
    exam = test_exam_service.get_exam(exam_id)
    assert exam is not None
    return {
        "employee_id": exam.employee_id,
        "employee_source": exam.employee_source,
        "employee_personal_number": exam.employee_personal_number,
        "employee_display_name": exam.employee_display_name,
        "employee_workplace_name": exam.employee_workplace_name,
        "exam_result": exam.exam_result,
        "status": exam.status,
    }


class EmployeeCentral8TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.workplace = settings_service.save_workplace(
            name=f"Provoz {self.marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.other_workplace = settings_service.save_workplace(
            name=f"Jiný provoz {self.marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.role = responsibility_role_service.create_role(name=f"Mistr {self.marker}")
        topic = oral_question_topic_service.create_topic(name=f"Okruh {self.marker}")
        oral_question_service.create_question(
            topic_id=topic.id,
            text=f"Otázka {self.marker}",
        )
        self.test = test_definition_service.create_test(
            name=f"Test {self.marker}",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_SINGLE,
            validity_value=2,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(topic_id=topic.id, question_count=1)],
        )

    def _employee(self, number: str, first: str, last: str, *, may_examine: bool = False):
        return test_employee_service.create_employee(
            personal_number=number,
            first_name=first,
            last_name=last,
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
            may_examine=may_examine,
            active=True,
        )

    def _worker(self, number: str, first: str, last: str, *, active: bool = True):
        return settings_service.save_worker(
            first_name=first,
            last_name=last,
            personal_number=number,
            workplace_id=self.other_workplace.id,
            active=active,
            is_thp=False,
            performs_controls=False,
            may_examine=False,
        )

    def _worker_at(self, worker_id: int, number: str, first: str, last: str):
        """Založí centrálního zaměstnance s daným id, i když ho řada už obsadila jinde."""
        if settings_service.get_worker_by_id(worker_id) is not None:
            self.fail("Číslo už v centrální evidenci patří jiné osobě.")
        connection = _connect()
        try:
            connection.execute(
                """
                INSERT INTO thp_workers (
                    id, title_before, first_name, last_name, title_after,
                    position, phone, email, personal_number, workplace_id,
                    is_thp, may_examine, active, performs_controls, created_at
                ) VALUES (?, '', ?, ?, '', '', '', '', ?, ?, 0, 0, 1, 0, ?)
                """,
                (
                    worker_id,
                    first,
                    last,
                    number,
                    self.other_workplace.id,
                    datetime.now().isoformat(sep=" "),
                ),
            )
            connection.commit()
        finally:
            connection.close()
        worker = settings_service.get_worker_by_id(worker_id)
        assert worker is not None
        return worker

    def _prepare(self, employee, examiner):
        return test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=self.test.id,
            exam_date=date(2024, 6, 1),
            examiner_id=examiner.id,
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        )

    def _rows_for_test(self, *, today: date, include_inactive: bool = True):
        return [
            row
            for row in exam_validity_service.list_rows(
                today=today,
                include_inactive_employees=include_inactive,
            )
            if row.test_definition_id == self.test.id
        ]

    def test_same_numeric_id_without_link_stays_two_people(self) -> None:
        employee = self._employee(f"H-{self.marker}", "Jana", f"Historie{self.marker}")
        examiner = self._employee(
            f"EX-{self.marker}",
            "Petr",
            f"Zkouší{self.marker}",
            may_examine=True,
        )
        worker = self._worker_at(
            employee.id,
            f"C-{self.marker}",
            "Eva",
            f"Centrum{self.marker}",
        )
        self.assertEqual(employee.id, worker.id)

        historical = self._prepare(employee, examiner)
        _complete_exam(
            historical.id,
            finished=datetime(2024, 6, 1, 9, 0),
            valid_until=date(2027, 6, 1),
        )
        central_id = _clone_exam(
            historical.id,
            employee_id=worker.id,
            employee_source=EMPLOYEE_SOURCE_THP_WORKER,
        )
        _complete_exam(
            central_id,
            finished=datetime(2025, 6, 1, 9, 0),
            valid_until=date(2028, 6, 1),
        )
        before = _snapshot_fields(historical.id)

        today = date(2026, 1, 1)
        rows = self._rows_for_test(today=today)
        by_source = {row.employee_source: row for row in rows}
        self.assertEqual(set(by_source), {
            EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            EMPLOYEE_SOURCE_THP_WORKER,
        })
        self.assertEqual(by_source[EMPLOYEE_SOURCE_TEST_EMPLOYEE].employee_id, employee.id)
        self.assertEqual(by_source[EMPLOYEE_SOURCE_THP_WORKER].employee_id, worker.id)
        self.assertEqual(
            by_source[EMPLOYEE_SOURCE_TEST_EMPLOYEE].employee_name,
            employee.display_name,
        )
        self.assertEqual(
            by_source[EMPLOYEE_SOURCE_THP_WORKER].employee_name,
            worker.display_name,
        )
        self.assertEqual(
            by_source[EMPLOYEE_SOURCE_THP_WORKER].personal_number,
            f"C-{self.marker}",
        )
        self.assertEqual(
            by_source[EMPLOYEE_SOURCE_THP_WORKER].workplace_name,
            self.other_workplace.name,
        )
        summary = exam_retraining_summary(rows)
        self.assertEqual(summary.valid_count, 2)

        exam_validity_service.stop_tracking(
            employee.id,
            self.test.id,
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        )
        stopped = {
            (row["employee_source"], row["employee_id"])
            for row in _tracking_rows()
            if row["test_definition_id"] == self.test.id
        }
        self.assertEqual(stopped, {(EMPLOYEE_SOURCE_TEST_EMPLOYEE, employee.id)})
        after_stop = {
            row.employee_source: row.tracked
            for row in self._rows_for_test(today=today)
        }
        self.assertFalse(after_stop[EMPLOYEE_SOURCE_TEST_EMPLOYEE])
        self.assertTrue(after_stop[EMPLOYEE_SOURCE_THP_WORKER])
        self.assertEqual(_snapshot_fields(historical.id), before)

    def test_linked_employee_has_one_validity_and_shared_tracking(self) -> None:
        employee = self._employee(f"H-{self.marker}", "Jana", f"Historie{self.marker}")
        examiner = self._employee(
            f"EX-{self.marker}",
            "Petr",
            f"Zkouší{self.marker}",
            may_examine=True,
        )
        worker = self._worker(f"C-{self.marker}", "Eva", f"Centrum{self.marker}")
        employee_central_link_service.link_existing(
            test_employee_id=employee.id,
            thp_worker_id=worker.id,
        )
        historical = self._prepare(employee, examiner)
        _complete_exam(
            historical.id,
            finished=datetime(2024, 6, 1, 9, 0),
            valid_until=date(2024, 12, 1),
        )
        before = _snapshot_fields(historical.id)
        central_id = _clone_exam(
            historical.id,
            employee_id=worker.id,
            employee_source=EMPLOYEE_SOURCE_THP_WORKER,
        )
        _complete_exam(
            central_id,
            finished=datetime(2025, 6, 1, 9, 0),
            valid_until=date(2027, 6, 1),
        )
        self.assertEqual(_snapshot_fields(historical.id), before)

        today = date(2026, 1, 1)
        rows = self._rows_for_test(today=today)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(row.employee_id, worker.id)
        self.assertEqual(row.employee_name, worker.display_name)
        self.assertEqual(row.personal_number, f"C-{self.marker}")
        self.assertEqual(row.workplace_id, self.other_workplace.id)
        self.assertTrue(row.employee_active)
        self.assertEqual(row.last_success_exam_id, central_id)
        self.assertEqual(row.state, EXAM_VALIDITY_STATE_VALID)
        self.assertEqual(row.valid_until, date(2027, 6, 1))
        summary = exam_retraining_summary(rows)
        self.assertEqual(summary.valid_count, 1)
        self.assertEqual(summary.expired_count, 0)

        exam_validity_service.stop_tracking(
            worker.id,
            self.test.id,
            employee_source=EMPLOYEE_SOURCE_THP_WORKER,
        )
        markers = {
            (item["employee_source"], item["employee_id"])
            for item in _tracking_rows()
            if item["test_definition_id"] == self.test.id
        }
        self.assertEqual(
            markers,
            {
                (EMPLOYEE_SOURCE_TEST_EMPLOYEE, employee.id),
                (EMPLOYEE_SOURCE_THP_WORKER, worker.id),
            },
        )
        self.assertFalse(self._rows_for_test(today=today)[0].tracked)
        hidden = exam_retraining_summary(self._rows_for_test(today=today))
        self.assertEqual(hidden.valid_count, 0)

        fresh = self._prepare(employee, examiner)
        self.assertEqual(fresh.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertEqual(fresh.employee_id, employee.id)
        self.assertEqual(
            [
                item
                for item in _tracking_rows()
                if item["test_definition_id"] == self.test.id
            ],
            [],
        )
        self.assertTrue(self._rows_for_test(today=today)[0].tracked)
        self.assertEqual(_snapshot_fields(historical.id), before)

        settings_service.save_worker(id=worker.id, active=False)
        active_rows = self._rows_for_test(today=today, include_inactive=False)
        self.assertEqual(active_rows, [])
        inactive_rows = self._rows_for_test(today=today, include_inactive=True)
        self.assertEqual(len(inactive_rows), 1)
        self.assertFalse(inactive_rows[0].employee_active)

    def test_unlinked_history_keeps_its_record_and_protocol(self) -> None:
        employee = self._employee(f"H-{self.marker}", "Jana", f"Historie{self.marker}")
        examiner = self._employee(
            f"EX-{self.marker}",
            "Petr",
            f"Zkouší{self.marker}",
            may_examine=True,
        )
        worker = self._worker(f"C-{self.marker}", "Eva", f"Centrum{self.marker}")
        historical = self._prepare(employee, examiner)
        _complete_exam(
            historical.id,
            finished=datetime(2024, 6, 1, 9, 0),
            valid_until=date(2024, 7, 1),
        )
        before = _snapshot_fields(historical.id)
        target = _TMP / f"protokol-{self.marker}.odt"
        exported = exam_protocol_export_service.export(historical.id, target)
        with zipfile.ZipFile(exported) as package:
            content = package.read("content.xml").decode("utf-8")
        self.assertIn(f"H-{self.marker}", content)
        self.assertIn(employee.display_name, content)
        self.assertNotIn(worker.display_name, content)

        today = date(2026, 1, 1)
        rows = self._rows_for_test(today=today)
        historical_rows = [
            row
            for row in rows
            if row.employee_source == EMPLOYEE_SOURCE_TEST_EMPLOYEE
            and row.employee_id == employee.id
        ]
        self.assertEqual(len(historical_rows), 1)
        self.assertEqual(historical_rows[0].employee_name, employee.display_name)
        self.assertEqual(historical_rows[0].personal_number, f"H-{self.marker}")
        self.assertEqual(historical_rows[0].state, EXAM_VALIDITY_STATE_EXPIRED)
        self.assertEqual(historical_rows[0].last_success_exam_id, historical.id)
        self.assertEqual(_snapshot_fields(historical.id), before)
        with zipfile.ZipFile(exported) as package:
            again = package.read("content.xml").decode("utf-8")
        self.assertEqual(again, content)
