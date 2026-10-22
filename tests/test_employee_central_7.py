"""EMPLOYEE-CENTRAL-7: identita sledování platnosti včetně zdroje."""

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

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-7-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

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
    from moduly.testy.sluzby.test_exam_service import test_exam_service


def _db_path() -> Path:
    return Path(storage_module.storage_service.database_path)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(_db_path()))
    connection.row_factory = sqlite3.Row
    return connection


def _rows(table: str) -> dict[int, dict]:
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


def _identity() -> dict:
    connection = _connect()
    try:
        unique_keys = []
        for index in connection.execute(
            'PRAGMA index_list("test_exam_validity_tracking")'
        ):
            if int(index[2]) != 1:
                continue
            columns = tuple(
                row[2]
                for row in connection.execute(f'PRAGMA index_info("{index[1]}")')
            )
            if columns != ("id",):
                unique_keys.append(columns)
        foreign_keys = [
            (row[3], row[2])
            for row in connection.execute(
                'PRAGMA foreign_key_list("test_exam_validity_tracking")'
            )
        ]
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' "
            "AND name = 'test_exam_validity_tracking'"
        ).fetchone()[0]
        return {
            "unique": unique_keys,
            "foreign_keys": foreign_keys,
            "schema": schema,
        }
    finally:
        connection.close()


def _install_old_identity() -> None:
    """Vrátí tabulku do podoby před rozšířením jedinečnosti."""
    stored = list(_rows("test_exam_validity_tracking").values())
    connection = _connect()
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            """
            CREATE TABLE test_exam_validity_tracking_old (
                id INTEGER NOT NULL PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                employee_source VARCHAR(20) NOT NULL DEFAULT 'test_employee',
                test_definition_id INTEGER NOT NULL,
                CONSTRAINT uq_test_exam_validity_tracking_pair
                    UNIQUE (employee_id, test_definition_id),
                CONSTRAINT ck_test_exam_validity_tracking_employee_source
                    CHECK (employee_source IN ('test_employee', 'thp_worker')),
                FOREIGN KEY(employee_id) REFERENCES test_employees (id),
                FOREIGN KEY(test_definition_id) REFERENCES test_definitions (id)
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO test_exam_validity_tracking_old (
                id, employee_id, employee_source, test_definition_id
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["employee_id"],
                    row["employee_source"],
                    row["test_definition_id"],
                )
                for row in stored
            ],
        )
        connection.execute("DROP TABLE test_exam_validity_tracking")
        connection.execute(
            "ALTER TABLE test_exam_validity_tracking_old "
            "RENAME TO test_exam_validity_tracking"
        )
        connection.commit()
    finally:
        connection.close()


class EmployeeCentral7TestCase(unittest.TestCase):
    def setUp(self) -> None:
        marker = uuid.uuid4().hex[:8]
        self.marker = marker
        workplace = settings_service.save_workplace(
            name=f"Provoz {marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        role = responsibility_role_service.create_role(name=f"Mistr {marker}")
        self.employee = test_employee_service.create_employee(
            personal_number=f"PL-{marker}",
            first_name="Jana",
            last_name=f"Malá{marker}",
            title_before="Bc.",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
            active=True,
        )
        examiner = test_employee_service.create_employee(
            personal_number=f"EX-{marker}",
            first_name="Petr",
            last_name=f"Zkouší{marker}",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
            may_examine=True,
            active=True,
        )
        topic = oral_question_topic_service.create_topic(name=f"Okruh {marker}")
        oral_question_service.create_question(
            topic_id=topic.id,
            text=f"Otázka {marker}",
        )
        self.test = test_definition_service.create_test(
            name=f"Test {marker}",
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
            examiner_id=examiner.id,
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        )
        exam_validity_service.stop_tracking(self.employee.id, self.test.id)

    def test_migration_keeps_rows_and_services(self) -> None:
        fresh = _identity()
        self.assertEqual(
            fresh["unique"],
            [("employee_source", "employee_id", "test_definition_id")],
        )
        self.assertNotIn(("employee_id", "test_employees"), fresh["foreign_keys"])
        self.assertIn(("test_definition_id", "test_definitions"), fresh["foreign_keys"])

        before_tracking = _rows("test_exam_validity_tracking")
        before_exams = _rows("test_exams")
        historical = before_tracking[
            next(iter(before_tracking))
        ]
        self.assertEqual(historical["employee_source"], EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertEqual(historical["employee_id"], self.employee.id)
        self.assertEqual(historical["test_definition_id"], self.test.id)

        _install_old_identity()
        old = _identity()
        self.assertEqual(old["unique"], [("employee_id", "test_definition_id")])
        self.assertIn(("employee_id", "test_employees"), old["foreign_keys"])

        initialize_database()
        migrated = _rows("test_exam_validity_tracking")
        self.assertEqual(migrated, before_tracking)
        self.assertEqual(_rows("test_exams"), before_exams)
        current = _identity()
        self.assertEqual(current["unique"], fresh["unique"])
        self.assertNotIn(("employee_id", "test_employees"), current["foreign_keys"])
        self.assertIn(("test_definition_id", "test_definitions"), current["foreign_keys"])
        self.assertIn("ck_test_exam_validity_tracking_employee_source", current["schema"])
        self.assertIn("PRIMARY KEY", current["schema"])

        initialize_database()
        self.assertEqual(_rows("test_exam_validity_tracking"), before_tracking)
        self.assertEqual(_rows("test_exams"), before_exams)

        connection = _connect()
        try:
            connection.execute(
                """
                UPDATE test_exam_validity_tracking
                SET employee_source = ?
                WHERE id = ?
                """,
                (EMPLOYEE_SOURCE_THP_WORKER, historical["id"]),
            )
            connection.commit()
        finally:
            connection.close()
        initialize_database()
        kept = _rows("test_exam_validity_tracking")[historical["id"]]
        self.assertEqual(kept["employee_source"], EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(kept["employee_id"], self.employee.id)
        self.assertEqual(kept["test_definition_id"], self.test.id)
        connection = _connect()
        try:
            connection.execute(
                """
                UPDATE test_exam_validity_tracking
                SET employee_source = ?
                WHERE id = ?
                """,
                (EMPLOYEE_SOURCE_TEST_EMPLOYEE, historical["id"]),
            )
            connection.commit()
        finally:
            connection.close()

        self._assert_source_uniqueness(historical)
        self._assert_historical_tracking_still_works(before_exams)

    def _assert_source_uniqueness(self, historical: dict) -> None:
        connection = _connect()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO test_exam_validity_tracking (
                        employee_id, employee_source, test_definition_id
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        historical["employee_id"],
                        EMPLOYEE_SOURCE_TEST_EMPLOYEE,
                        historical["test_definition_id"],
                    ),
                )
                connection.commit()
            connection.rollback()
            connection.execute(
                """
                INSERT INTO test_exam_validity_tracking (
                    employee_id, employee_source, test_definition_id
                ) VALUES (?, ?, ?)
                """,
                (
                    historical["employee_id"],
                    EMPLOYEE_SOURCE_THP_WORKER,
                    historical["test_definition_id"],
                ),
            )
            connection.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO test_exam_validity_tracking (
                        employee_id, employee_source, test_definition_id
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        historical["employee_id"],
                        EMPLOYEE_SOURCE_THP_WORKER,
                        historical["test_definition_id"],
                    ),
                )
                connection.commit()
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    UPDATE test_exam_validity_tracking
                    SET employee_source = 'jiny'
                    WHERE employee_source = ?
                    """,
                    (EMPLOYEE_SOURCE_THP_WORKER,),
                )
                connection.commit()
            connection.rollback()
            connection.execute(
                """
                DELETE FROM test_exam_validity_tracking
                WHERE employee_source = ?
                """,
                (EMPLOYEE_SOURCE_THP_WORKER,),
            )
            connection.commit()
        finally:
            connection.close()

    def _assert_historical_tracking_still_works(self, exams_before: dict) -> None:
        rows = [
            row
            for row in exam_validity_service.list_rows(
                today=date(2024, 7, 1),
                include_inactive_employees=True,
            )
            if row.employee_id == self.employee.id
            and row.test_definition_id == self.test.id
        ]
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].tracked)
        self.assertEqual(rows[0].personal_number, f"PL-{self.marker}")
        self.assertEqual(rows[0].employee_name, self.employee.display_name)

        exam_validity_service.resume_tracking(self.employee.id, self.test.id)
        resumed = [
            row
            for row in exam_validity_service.list_rows(
                today=date(2024, 7, 1),
                include_inactive_employees=True,
            )
            if row.employee_id == self.employee.id
            and row.test_definition_id == self.test.id
        ]
        self.assertEqual(len(resumed), 1)
        self.assertTrue(resumed[0].tracked)
        self.assertEqual(_rows("test_exams"), exams_before)

        exam_validity_service.stop_tracking(self.employee.id, self.test.id)
        stored = list(_rows("test_exam_validity_tracking").values())
        matched = [
            row
            for row in stored
            if row["employee_id"] == self.employee.id
            and row["test_definition_id"] == self.test.id
        ]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["employee_source"], EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        opened = test_exam_service.get_exam(self.exam.id)
        assert opened is not None
        self.assertEqual(opened.employee_id, self.employee.id)
        self.assertEqual(opened.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertEqual(opened.employee_display_name, self.employee.display_name)
