"""EMPLOYEE-CENTRAL-6: zdroj zaměstnance u historických zkoušek."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-6-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.employee_central_link_service import (
        EmployeeLinkError,
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
        EXAMINER_MODE_SINGLE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_MODE_ELECTRONIC,
        WRITTEN_RESULT_PASSED,
    )
    from moduly.testy.sluzby.exam_protocol_export_service import (
        exam_protocol_export_service,
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
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog


_SOURCE_TABLES = (
    "test_exams",
    "test_exam_examiners",
    "test_exam_validity_tracking",
)


def _db_path() -> Path:
    return Path(storage_module.storage_service.database_path)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(_db_path()))
    connection.row_factory = sqlite3.Row
    return connection


def _table_rows(table: str) -> dict[int, dict]:
    connection = _connect()
    try:
        columns = [
            row[1]
            for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        ]
        stored = {}
        for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY id'):
            stored[int(row["id"])] = {column: row[column] for column in columns}
        return stored
    finally:
        connection.close()


def _legacy_create_sql(table: str, columns: list[sqlite3.Row]) -> str:
    definitions = []
    for column in columns:
        name, col_type, notnull, default, primary_key = (
            column[1],
            column[2],
            column[3],
            column[4],
            column[5],
        )
        piece = f'"{name}" {col_type or "TEXT"}'
        if primary_key:
            piece += " PRIMARY KEY"
        elif notnull:
            piece += " NOT NULL"
        if default is not None:
            piece += f" DEFAULT {default}"
        definitions.append(piece)
    return f'CREATE TABLE "{table}" ({", ".join(definitions)})'


def _drop_source(table: str) -> None:
    """Napodobí starou tabulku bez sloupce zdroje a zachová řádky i primární klíč."""
    connection = _connect()
    kept = f"{table}__kept"
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        columns = [
            row
            for row in connection.execute(f'PRAGMA table_info("{table}")')
            if row[1] != "employee_source"
        ]
        names = ", ".join(f'"{column[1]}"' for column in columns)
        connection.execute(f'ALTER TABLE "{table}" RENAME TO "{kept}"')
        connection.execute(_legacy_create_sql(table, columns))
        connection.execute(
            f'INSERT INTO "{table}" ({names}) SELECT {names} FROM "{kept}"'
        )
        connection.execute(f'DROP TABLE "{kept}"')
        connection.commit()
    except Exception:
        present = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        kept_present = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (kept,),
        ).fetchone()
        if present is None and kept_present is not None:
            connection.execute(f'ALTER TABLE "{kept}" RENAME TO "{table}"')
            connection.commit()
        raise
    finally:
        connection.close()


class EmployeeCentral6TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.workplace = settings_service.save_workplace(
            name=f"Provoz {self.marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.role = responsibility_role_service.create_role(name=f"Mistr {self.marker}")
        self.employee = test_employee_service.create_employee(
            personal_number=f"HIST-{self.marker}",
            first_name="Jana",
            last_name=f"Malá{self.marker}",
            title_before="Bc.",
            title_after="DiS.",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
            may_examine=False,
            active=True,
        )
        self.examiner = test_employee_service.create_employee(
            personal_number=f"EX-{self.marker}",
            first_name="Petr",
            last_name=f"Zkouší{self.marker}",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
            may_examine=True,
            active=True,
        )
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
        self.exam = test_exam_service.prepare_exam(
            employee_id=self.employee.id,
            test_id=self.test.id,
            exam_date=date(2024, 6, 1),
            examiner_id=self.examiner.id,
        )
        exam_validity_service.stop_tracking(self.employee.id, self.test.id)
        connection = _connect()
        try:
            connection.execute(
                """
                UPDATE test_exams
                SET status = ?, written_mode = ?, written_result = ?, exam_result = ?,
                    written_question_count = 3, written_correct_count = 3,
                    written_incorrect_count = 0, written_unanswered_count = 0,
                    written_allowed_wrong_answers = 1
                WHERE id = ?
                """,
                (
                    EXAM_STATUS_COMPLETED,
                    WRITTEN_MODE_ELECTRONIC,
                    WRITTEN_RESULT_PASSED,
                    WRITTEN_RESULT_PASSED,
                    self.exam.id,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def test_migration_keeps_history_and_marks_existing_rows(self) -> None:
        before_employees = _table_rows("test_employees")
        before = {table: _table_rows(table) for table in _SOURCE_TABLES}
        for table, rows in before.items():
            self.assertGreaterEqual(len(rows), 1)
            for row in rows.values():
                self.assertEqual(row["employee_source"], EMPLOYEE_SOURCE_TEST_EMPLOYEE)

        for table in _SOURCE_TABLES:
            _drop_source(table)
        initialize_database()

        after = {table: _table_rows(table) for table in _SOURCE_TABLES}
        self._assert_history_preserved(before, after)
        self.assertEqual(_table_rows("test_employees"), before_employees)

        initialize_database()
        repeated = {table: _table_rows(table) for table in _SOURCE_TABLES}
        self.assertEqual(repeated, after)

        connection = _connect()
        try:
            connection.execute(
                """
                UPDATE test_exams
                SET employee_source = ?
                WHERE id = ?
                """,
                (EMPLOYEE_SOURCE_THP_WORKER, self.exam.id),
            )
            connection.commit()
        finally:
            connection.close()
        kept_id = _table_rows("test_exams")[self.exam.id]["employee_id"]
        initialize_database()
        migrated = _table_rows("test_exams")[self.exam.id]
        self.assertEqual(migrated["employee_source"], EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(migrated["employee_id"], kept_id)
        self.assertEqual(
            migrated["employee_display_name"],
            before["test_exams"][self.exam.id]["employee_display_name"],
        )
        self.assertEqual(migrated["exam_result"], WRITTEN_RESULT_PASSED)

        connection = _connect()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    UPDATE test_exams
                    SET employee_source = 'jiny'
                    WHERE id = ?
                    """,
                    (self.exam.id,),
                )
                connection.commit()
            connection.rollback()
        finally:
            connection.close()

    def test_historical_exam_detail_result_protocol_and_validity(self) -> None:
        before = {table: _table_rows(table) for table in _SOURCE_TABLES}
        for table in _SOURCE_TABLES:
            _drop_source(table)
        initialize_database()

        exam = test_exam_service.get_exam(self.exam.id)
        assert exam is not None
        self.assertEqual(exam.employee_id, self.employee.id)
        self.assertEqual(exam.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertEqual(exam.employee_personal_number, f"HIST-{self.marker}")
        self.assertEqual(exam.employee_display_name, self.employee.display_name)
        self.assertEqual(exam.exam_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(exam.written_result, WRITTEN_RESULT_PASSED)
        examiners = test_exam_service.get_examiners(exam.id)
        self.assertEqual(len(examiners), 1)
        self.assertEqual(examiners[0].employee_id, self.examiner.id)
        self.assertEqual(examiners[0].employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertEqual(examiners[0].display_name, self.examiner.display_name)

        dialog = TestExamDetailDialog()
        dialog.load_exam(exam.id)
        self.assertIn(self.employee.display_name, dialog.summary.text())
        self.assertIn(f"HIST-{self.marker}", dialog.summary.text())
        self.assertIn(self.examiner.display_name, dialog.summary.text())
        self.assertIn("Vyhověl(a)", dialog.written_summary.text())
        self.assertIn("Výsledek zkoušky: Vyhověl(a)", dialog.written_summary.text())
        dialog.close()

        target = _TMP / f"protokol-{self.marker}.odt"
        exported = exam_protocol_export_service.export(exam.id, target)
        with zipfile.ZipFile(exported) as package:
            content = package.read("content.xml").decode("utf-8")
        self.assertIn(f"HIST-{self.marker}", content)
        self.assertIn(self.employee.display_name, content)
        self.assertIn(self.examiner.display_name, content)

        rows = exam_validity_service.list_rows(
            today=date(2024, 7, 1),
            include_inactive_employees=True,
        )
        matched = [
            row
            for row in rows
            if row.employee_id == self.employee.id
            and row.test_definition_id == self.test.id
        ]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].personal_number, f"HIST-{self.marker}")
        self.assertEqual(matched[0].employee_name, self.employee.display_name)
        self.assertFalse(matched[0].tracked)

        after = {table: _table_rows(table) for table in _SOURCE_TABLES}
        self._assert_history_preserved(before, after)

        fresh = test_exam_service.prepare_exam(
            employee_id=self.employee.id,
            test_id=self.test.id,
            exam_date=date(2025, 1, 15),
            examiner_id=self.examiner.id,
        )
        stored = test_exam_service.get_exam(fresh.id)
        assert stored is not None
        self.assertEqual(stored.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertEqual(stored.employee_id, self.employee.id)

    def test_unlink_allows_history_and_refuses_central_exam(self) -> None:
        worker = settings_service.save_worker(
            first_name="Eva",
            last_name=f"Centrum{self.marker}",
            personal_number=f"C-{self.marker}",
        )
        employee_central_link_service.link_existing(
            test_employee_id=self.employee.id,
            thp_worker_id=worker.id,
        )
        removed = employee_central_link_service.unlink(
            test_employee_id=self.employee.id,
            thp_worker_id=worker.id,
        )
        self.assertTrue(removed.removed)
        self.assertIsNone(
            employee_central_link_service.get_by_test_employee(self.employee.id)
        )
        self.assertEqual(
            test_exam_service.get_exam(self.exam.id).employee_id,
            self.employee.id,
        )

        employee_central_link_service.link_existing(
            test_employee_id=self.employee.id,
            thp_worker_id=worker.id,
        )
        connection = _connect()
        try:
            connection.execute(
                """
                UPDATE test_exams
                SET employee_source = ?, employee_id = ?
                WHERE id = ?
                """,
                (EMPLOYEE_SOURCE_THP_WORKER, worker.id, self.exam.id),
            )
            connection.commit()
        finally:
            connection.close()
        try:
            with self.assertRaises(EmployeeLinkError) as refused:
                employee_central_link_service.unlink(
                    test_employee_id=self.employee.id,
                    thp_worker_id=worker.id,
                )
            self.assertIn("nová zkouška", str(refused.exception))
            kept = employee_central_link_service.get_by_test_employee(self.employee.id)
            assert kept is not None
            self.assertEqual(kept.thp_worker_id, worker.id)
        finally:
            connection = _connect()
            try:
                connection.execute(
                    """
                    UPDATE test_exams
                    SET employee_source = ?, employee_id = ?
                    WHERE id = ?
                    """,
                    (EMPLOYEE_SOURCE_TEST_EMPLOYEE, self.employee.id, self.exam.id),
                )
                connection.commit()
            finally:
                connection.close()

        connection = _connect()
        try:
            connection.execute("ALTER TABLE test_exams ADD COLUMN transfer_note TEXT")
            connection.commit()
        finally:
            connection.close()
        try:
            with self.assertRaises(EmployeeLinkError) as unknown:
                employee_central_link_service.unlink(
                    test_employee_id=self.employee.id,
                    thp_worker_id=worker.id,
                )
            self.assertIn("nelze spolehlivě ověřit", str(unknown.exception))
        finally:
            connection = _connect()
            try:
                connection.execute("ALTER TABLE test_exams DROP COLUMN transfer_note")
                connection.commit()
            finally:
                connection.close()

    def _assert_history_preserved(self, before: dict, after: dict) -> None:
        for table in _SOURCE_TABLES:
            self.assertEqual(set(before[table]), set(after[table]))
            for row_id, original in before[table].items():
                current = after[table][row_id]
                for column, value in original.items():
                    if column == "employee_source":
                        continue
                    self.assertEqual(current[column], value, f"{table}.{column}")
                self.assertEqual(
                    current["employee_source"],
                    EMPLOYEE_SOURCE_TEST_EMPLOYEE,
                )
                self.assertEqual(current["employee_id"], original["employee_id"])
