"""EMPLOYEE-CENTRAL-1: sloupce centrální evidence na thp_workers."""

from __future__ import annotations

import importlib
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-1-"))

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
    from tests.historical_test_employee import (
        seed_historical_test_employee,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service


_LEGACY_COLUMNS = (
    "id",
    "title_before",
    "first_name",
    "last_name",
    "title_after",
    "position",
    "phone",
    "email",
    "active",
    "performs_controls",
    "created_at",
)


def _db_path() -> Path:
    return Path(storage_module.storage_service.database_path)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(_db_path()))
    connection.row_factory = sqlite3.Row
    return connection


def _columns(table: str) -> list[str]:
    connection = _connect()
    try:
        return [
            row[1]
            for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        ]
    finally:
        connection.close()


def _select_all(table: str) -> list[tuple]:
    connection = _connect()
    try:
        return list(connection.execute(f'SELECT * FROM "{table}" ORDER BY id'))
    finally:
        connection.close()


def _index_sql(name: str) -> str:
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
            (name,),
        ).fetchone()
        return "" if row is None or row[0] is None else str(row[0])
    finally:
        connection.close()


class EmployeeCentral1TestCase(unittest.TestCase):
    def test_fresh_schema_and_repeated_start(self) -> None:
        self.assertIn("personal_number", _columns("thp_workers"))
        self.assertIn("workplace_id", _columns("thp_workers"))
        self.assertIn("is_thp", _columns("thp_workers"))
        self.assertIn("may_examine", _columns("thp_workers"))
        self.assertIn("updated_at", _columns("thp_workers"))
        self.assertIn("position", _columns("thp_workers"))
        self.assertNotIn("is_thp", _columns("test_employees"))
        self.assertNotIn("personal_number", _columns("thp_worker_roles"))
        connection = _connect()
        try:
            worker_targets = {
                row[2]
                for row in connection.execute(
                    "PRAGMA foreign_key_list(thp_workers)"
                ).fetchall()
            }
            role_targets = {
                row[2]
                for row in connection.execute(
                    "PRAGMA foreign_key_list(thp_worker_roles)"
                ).fetchall()
            }
        finally:
            connection.close()
        self.assertIn("workplaces", worker_targets)
        self.assertIn("thp_workers", role_targets)
        self.assertIn("responsibility_roles", role_targets)
        self.assertEqual(
            _columns("thp_worker_roles"),
            [
                "id",
                "thp_worker_id",
                "responsibility_role_id",
                "sort_order",
            ],
        )
        index_sql = _index_sql("uq_thp_workers_personal_number").casefold()
        self.assertIn("unique", index_sql)
        self.assertIn("personal_number", index_sql)
        self.assertIn("where", index_sql)

        before_employees = _select_all("test_employees")
        before_exams = _select_all("test_exams")
        initialize_database()
        self.assertEqual(_select_all("test_employees"), before_employees)
        self.assertEqual(_select_all("test_exams"), before_exams)
        self.assertEqual(_columns("thp_worker_roles")[1], "thp_worker_id")

    def test_save_worker_keeps_previous_service_contract(self) -> None:
        marker = uuid.uuid4().hex[:8]
        worker = settings_service.save_worker(
            title_before="Ing.",
            first_name=f"Adam{marker}",
            last_name="Dvořák",
            title_after="Ph.D.",
            position="Bezpečnostní technik",
            phone="777111222",
            email=f"adam{marker}@example.test",
            performs_controls=True,
        )
        self.assertTrue(worker.is_thp)
        self.assertFalse(worker.may_examine)
        self.assertIsNone(worker.personal_number)
        self.assertIsNone(worker.workplace_id)
        self.assertEqual(worker.position, "Bezpečnostní technik")
        self.assertIsNotNone(worker.updated_at)

        renamed = settings_service.save_worker(
            id=worker.id,
            first_name=f"Adam{marker}",
            last_name="Dvořáková",
            position="Bezpečnostní technik",
        )
        self.assertEqual(renamed.last_name, "Dvořáková")
        self.assertTrue(renamed.is_thp)
        self.assertFalse(renamed.may_examine)
        self.assertIsNone(renamed.personal_number)
        self.assertEqual(renamed.position, "Bezpečnostní technik")
        self.assertEqual(renamed.phone, "777111222")
        self.assertTrue(renamed.performs_controls)

        self.assertTrue(settings_service.deactivate_worker(worker.id))
        inactive = settings_service.get_worker_by_id(worker.id)
        self.assertIsNotNone(inactive)
        assert inactive is not None
        self.assertFalse(inactive.active)
        self.assertTrue(inactive.is_thp)
        self.assertNotIn(
            worker.id,
            [item.id for item in settings_service.get_workers()],
        )
        self.assertIn(
            worker.id,
            [item.id for item in settings_service.get_workers(include_inactive=True)],
        )
        self.assertNotIn(
            worker.id,
            [item.id for item in settings_service.get_workers_for_controls()],
        )

        self.assertTrue(settings_service.activate_worker(worker.id))
        active = settings_service.get_worker_by_id(worker.id)
        assert active is not None
        self.assertTrue(active.active)
        self.assertIn(
            worker.id,
            [item.id for item in settings_service.get_workers_for_controls()],
        )

    def test_personal_number_unique_only_when_filled(self) -> None:
        marker = uuid.uuid4().hex[:8]
        first = settings_service.save_worker(
            first_name="Ema",
            last_name=f"První{marker}",
        )
        second = settings_service.save_worker(
            first_name="Ema",
            last_name=f"Druhá{marker}",
        )
        self.assertIsNone(first.personal_number)
        self.assertIsNone(second.personal_number)

        number = f"OC-{marker}"
        connection = _connect()
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                "UPDATE thp_workers SET personal_number = '' WHERE id = ?",
                (first.id,),
            )
            connection.execute(
                "UPDATE thp_workers SET personal_number = '' WHERE id = ?",
                (second.id,),
            )
            connection.execute(
                "UPDATE thp_workers SET personal_number = ? WHERE id = ?",
                (number, first.id),
            )
            connection.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE thp_workers SET personal_number = ? WHERE id = ?",
                    (number, second.id),
                )
                connection.commit()
            connection.rollback()
        finally:
            connection.close()

        stored = settings_service.get_worker_by_id(second.id)
        assert stored is not None
        self.assertEqual(stored.personal_number, "")
        occupied = settings_service.get_worker_by_id(first.id)
        assert occupied is not None
        self.assertEqual(occupied.personal_number, number)

    def test_worker_can_have_several_roles_without_changing_position(self) -> None:
        marker = uuid.uuid4().hex[:8]
        worker = settings_service.save_worker(
            first_name="Role",
            last_name=f"Test{marker}",
            position="Volný text funkce",
        )
        roles = responsibility_role_service.get_all(include_inactive=True)
        self.assertGreaterEqual(len(roles), 2)
        connection = _connect()
        try:
            connection.execute(
                """
                INSERT INTO thp_worker_roles
                    (thp_worker_id, responsibility_role_id, sort_order)
                VALUES (?, ?, 1), (?, ?, 2)
                """,
                (worker.id, roles[0].id, worker.id, roles[1].id),
            )
            connection.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO thp_worker_roles
                        (thp_worker_id, responsibility_role_id, sort_order)
                    VALUES (?, ?, 3)
                    """,
                    (worker.id, roles[0].id),
                )
                connection.commit()
            connection.rollback()
            stored_roles = connection.execute(
                """
                SELECT responsibility_role_id, sort_order
                FROM thp_worker_roles
                WHERE thp_worker_id = ?
                ORDER BY sort_order
                """,
                (worker.id,),
            ).fetchall()
        finally:
            connection.close()

        self.assertEqual(
            [(row[0], row[1]) for row in stored_roles],
            [(roles[0].id, 1), (roles[1].id, 2)],
        )
        reloaded = settings_service.get_worker_by_id(worker.id)
        assert reloaded is not None
        self.assertEqual(reloaded.position, "Volný text funkce")

        self.assertTrue(settings_service.deactivate_worker(worker.id))
        connection = _connect()
        try:
            remaining = connection.execute(
                "SELECT COUNT(*) FROM thp_worker_roles WHERE thp_worker_id = ?",
                (worker.id,),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(int(remaining[0]), 2)

    def test_legacy_database_migration_preserves_rows(self) -> None:
        marker = uuid.uuid4().hex[:8]
        workplace = settings_service.save_workplace(
            name=f"Provoz {marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        role = responsibility_role_service.get_all()[0]
        employee = seed_historical_test_employee(
            personal_number=f"TE-{marker}",
            first_name="Jana",
            last_name="Malá",
            title_before="Bc.",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
            may_examine=True,
        )
        worker = settings_service.save_worker(
            title_before="Ing.",
            first_name="Petr",
            last_name=f"Starý{marker}",
            title_after="CSc.",
            position="Vedoucí provozu",
            phone="601000111",
            email=f"petr{marker}@example.test",
            performs_controls=False,
            active=True,
        )
        created_at = "2024-05-01 08:30:00"
        connection = _connect()
        try:
            connection.execute(
                "UPDATE thp_workers SET created_at = ? WHERE id = ?",
                (created_at, worker.id),
            )
            definition = connection.execute(
                """
                INSERT INTO test_definitions (
                    name, description, active, uses_written, allowed_wrong_answers,
                    seconds_per_question, uses_oral, examiner_mode, validity_value,
                    validity_unit, created_at, updated_at
                ) VALUES (?, '', 1, 1, 1, 30, 0, 'single', 2, 'year', ?, ?)
                """,
                (f"Test {marker}", created_at, created_at),
            )
            exam = connection.execute(
                """
                INSERT INTO test_exams (
                    employee_id, test_definition_id, exam_date, status, examiner_mode,
                    employee_personal_number, employee_first_name, employee_last_name,
                    employee_title_before, employee_title_after, employee_display_name,
                    employee_workplace_name, employee_roles_text, test_name,
                    uses_written, uses_oral, allowed_wrong_answers, seconds_per_question,
                    written_duration_seconds, validity_value, validity_unit, created_at,
                    written_finish_reason, written_technical_detail
                ) VALUES (
                    ?, ?, '2024-06-01', 'prepared', 'single',
                    ?, 'Jana', 'Malá', 'Bc.', '', 'Bc. Jana Malá',
                    ?, ?, ?,
                    1, 0, 1, 30, 30, 2, 'year', ?,
                    '', ''
                )
                """,
                (
                    employee.id,
                    definition.lastrowid,
                    employee.personal_number,
                    workplace.name,
                    role.name,
                    f"Test {marker}",
                    created_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO test_exam_examiners (
                    exam_id, employee_id, display_name, role, position
                ) VALUES (?, ?, 'Bc. Jana Malá', 'examiner', 1)
                """,
                (exam.lastrowid, employee.id),
            )
            connection.commit()
            exam_id = int(exam.lastrowid)
        finally:
            connection.close()

        employees_before = _select_all("test_employees")
        employee_roles_before = _select_all("test_employee_roles")
        exams_before = _select_all("test_exams")
        examiners_before = _select_all("test_exam_examiners")
        legacy_before = self._legacy_rows()

        self._downgrade_thp_workers()
        self.assertNotIn("personal_number", _columns("thp_workers"))
        self.assertFalse(_columns("thp_worker_roles"))

        initialize_database()

        self.assertEqual(self._legacy_rows(), legacy_before)
        self.assertEqual(_select_all("test_employees"), employees_before)
        self.assertEqual(_select_all("test_employee_roles"), employee_roles_before)
        self.assertEqual(_select_all("test_exams"), exams_before)
        self.assertEqual(_select_all("test_exam_examiners"), examiners_before)

        migrated = settings_service.get_worker_by_id(worker.id)
        assert migrated is not None
        self.assertTrue(migrated.is_thp)
        self.assertFalse(migrated.may_examine)
        self.assertIsNone(migrated.personal_number)
        self.assertIsNone(migrated.workplace_id)
        self.assertEqual(migrated.position, "Vedoucí provozu")
        self.assertEqual(
            migrated.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            created_at,
        )
        connection = _connect()
        try:
            role_count = connection.execute(
                "SELECT COUNT(*) FROM thp_worker_roles WHERE thp_worker_id = ?",
                (worker.id,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(int(role_count), 0)

        connection = _connect()
        try:
            connection.execute(
                """
                UPDATE thp_workers
                SET personal_number = ?, workplace_id = ?, is_thp = 0,
                    may_examine = 1, updated_at = ?
                WHERE id = ?
                """,
                (f"KEEP-{marker}", workplace.id, "2025-01-02 09:00:00", worker.id),
            )
            connection.commit()
        finally:
            connection.close()

        initialize_database()

        self.assertEqual(self._legacy_rows(), legacy_before)
        self.assertEqual(_select_all("test_employees"), employees_before)
        self.assertEqual(_select_all("test_exams"), exams_before)
        kept = settings_service.get_worker_by_id(worker.id)
        assert kept is not None
        self.assertEqual(kept.personal_number, f"KEEP-{marker}")
        self.assertEqual(kept.workplace_id, workplace.id)
        self.assertFalse(kept.is_thp)
        self.assertTrue(kept.may_examine)
        self.assertEqual(
            kept.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "2025-01-02 09:00:00",
        )
        exam_row = next(row for row in _select_all("test_exams") if row[0] == exam_id)
        self.assertEqual(exam_row, next(row for row in exams_before if row[0] == exam_id))

    def test_empty_database_can_be_initialized_twice(self) -> None:
        from core.database.session import (
            dispose_database_engine,
            reconfigure_database_engine,
        )

        path = _db_path()
        aside = path.with_name(f"{path.name}.aside-{uuid.uuid4().hex}")
        dispose_database_engine()
        path.rename(aside)
        try:
            initialize_database()
            self.assertEqual(self._count("thp_workers"), 0)
            self.assertEqual(self._count("thp_worker_roles"), 0)
            self.assertEqual(self._count("test_employees"), 0)
            self.assertEqual(self._count("test_exams"), 0)
            self.assertIn("is_thp", _columns("thp_workers"))
            initialize_database()
            self.assertEqual(self._count("thp_workers"), 0)
            self.assertIn("personal_number", _columns("thp_workers"))
        finally:
            dispose_database_engine()
            if path.exists():
                path.unlink()
            aside.rename(path)
            reconfigure_database_engine(force=True)

    def _count(self, table: str) -> int:
        connection = _connect()
        try:
            return int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
        finally:
            connection.close()

    def _legacy_rows(self) -> list[tuple]:
        columns = ", ".join(_LEGACY_COLUMNS)
        connection = _connect()
        try:
            return list(
                connection.execute(
                    f"SELECT {columns} FROM thp_workers ORDER BY id"
                )
            )
        finally:
            connection.close()

    def _downgrade_thp_workers(self) -> None:
        from core.database.session import dispose_database_engine

        dispose_database_engine()
        connection = _connect()
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            rows = list(
                connection.execute(
                    f"SELECT {', '.join(_LEGACY_COLUMNS)} FROM thp_workers ORDER BY id"
                )
            )
            connection.execute("DROP TABLE IF EXISTS thp_worker_roles")
            connection.execute("DROP TABLE thp_workers")
            connection.execute(
                """
                CREATE TABLE thp_workers (
                    id INTEGER PRIMARY KEY,
                    title_before VARCHAR(50) DEFAULT '',
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    title_after VARCHAR(50) DEFAULT '',
                    position VARCHAR(150) DEFAULT '',
                    phone VARCHAR(50) DEFAULT '',
                    email VARCHAR(150) DEFAULT '',
                    active BOOLEAN DEFAULT 1,
                    performs_controls BOOLEAN DEFAULT 0,
                    created_at DATETIME
                )
                """
            )
            connection.executemany(
                f"""
                INSERT INTO thp_workers ({", ".join(_LEGACY_COLUMNS)})
                VALUES ({", ".join("?" for _ in _LEGACY_COLUMNS)})
                """,
                [tuple(row) for row in rows],
            )
            connection.commit()
        finally:
            connection.close()
