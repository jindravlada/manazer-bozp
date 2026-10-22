"""Předmigrační záloha existující databáze před schématem 4.1.3."""

from __future__ import annotations

import hashlib
import importlib
import shutil
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from core.backup import inspect_backup_integrity
from core.database.upgrade_guard import (
    PreMigrationBackupError,
    is_migration_in_progress,
    is_transition_complete,
    prepare_database_for_startup,
)
from moduly.nastaveni.sluzby.employee_central_413_schema_migration import (
    TRANSITION_ID,
    needs_employee_central_413_schema,
    schema_is_present,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _downgrade_employee_tables(path: Path) -> None:
    """Úplné aktuální schéma vrátí v tabulkách zaměstnanců a zkoušek do tvaru 4.1.2."""
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.executescript(
            """
            DROP TABLE IF EXISTS test_employee_central_links;
            DROP TABLE IF EXISTS thp_worker_roles;
            DROP TABLE IF EXISTS test_exam_validity_tracking;
            DROP TABLE IF EXISTS test_exam_examiners;
            DROP TABLE IF EXISTS test_exams;
            DROP TABLE IF EXISTS test_employees;
            DROP TABLE IF EXISTS thp_workers;

            INSERT INTO workplaces (
                item_type, name, address, note, active,
                audit_enabled, audit_interval_months, preferred_months_json,
                created_at
            ) VALUES (
                'operation', 'Provoz A', '', '', 1,
                1, 12, '[]', '2024-05-01 08:30:00'
            );

            INSERT INTO test_definitions (
                name, description, active, uses_written, allowed_wrong_answers,
                seconds_per_question, uses_oral, examiner_mode, validity_value,
                validity_unit, created_at, updated_at
            ) VALUES (
                'Periodické přezkoušení', '', 1, 1, 1,
                30, 0, 'single', 12,
                'months', '2024-05-01 08:30:00', '2024-05-01 08:30:00'
            );

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
            );
            INSERT INTO thp_workers (
                id, title_before, first_name, last_name, position, created_at
            ) VALUES (
                7, 'Ing.', 'Petr', 'Starý', 'Vedoucí', '2024-05-01 08:30:00'
            );

            CREATE TABLE test_employees (
                id INTEGER PRIMARY KEY,
                personal_number VARCHAR(50) NOT NULL UNIQUE,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                title_before VARCHAR(50) DEFAULT '',
                title_after VARCHAR(50) DEFAULT '',
                workplace_id INTEGER NOT NULL,
                may_examine BOOLEAN NOT NULL DEFAULT 0,
                active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME
            );
            INSERT INTO test_employees (
                id, personal_number, first_name, last_name, title_before,
                workplace_id, may_examine, active, created_at, updated_at
            ) VALUES (
                3, 'TE-413', 'Jana', 'Malá', 'Bc.',
                (SELECT id FROM workplaces WHERE name = 'Provoz A'),
                1, 1, '2024-05-01 08:30:00', '2024-05-01 08:30:00'
            );

            CREATE TABLE test_exams (
                id INTEGER PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                test_definition_id INTEGER NOT NULL,
                exam_date DATE NOT NULL,
                status VARCHAR(20) NOT NULL,
                examiner_mode VARCHAR(20) NOT NULL,
                employee_personal_number VARCHAR(50) NOT NULL,
                employee_first_name VARCHAR(100) NOT NULL,
                employee_last_name VARCHAR(100) NOT NULL,
                employee_display_name VARCHAR(300) NOT NULL,
                test_name VARCHAR(200) NOT NULL,
                validity_value INTEGER NOT NULL,
                validity_unit VARCHAR(20) NOT NULL,
                FOREIGN KEY(employee_id) REFERENCES test_employees(id),
                FOREIGN KEY(test_definition_id) REFERENCES test_definitions(id)
            );
            INSERT INTO test_exams (
                id, employee_id, test_definition_id, exam_date, status,
                examiner_mode, employee_personal_number, employee_first_name,
                employee_last_name, employee_display_name, test_name,
                validity_value, validity_unit
            ) VALUES (
                11, 3,
                (SELECT id FROM test_definitions WHERE name = 'Periodické přezkoušení'),
                '2024-06-01', 'dokonceno', 'single',
                'TE-413', 'Jana', 'Malá', 'Bc. Jana Malá',
                'Periodické přezkoušení', 12, 'months'
            );

            CREATE TABLE test_exam_validity_tracking (
                id INTEGER PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                test_definition_id INTEGER NOT NULL,
                UNIQUE (employee_id, test_definition_id),
                FOREIGN KEY(employee_id) REFERENCES test_employees(id),
                FOREIGN KEY(test_definition_id) REFERENCES test_definitions(id)
            );
            INSERT INTO test_exam_validity_tracking (
                id, employee_id, test_definition_id
            ) VALUES (
                1, 3,
                (SELECT id FROM test_definitions WHERE name = 'Periodické přezkoušení')
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def _column_names(path: Path, table_name: str) -> set[str]:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        rows = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        return {str(row[1]) for row in rows}
    finally:
        connection.close()


def _cell(path: Path, sql: str, params: tuple = ()) -> object:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        return connection.execute(sql, params).fetchone()[0]
    finally:
        connection.close()


def _backup_database(package: Path, destination: Path) -> None:
    with zipfile.ZipFile(package) as archive:
        destination.write_bytes(archive.read("database/manager_bozp.db"))


class EmployeeCentral413BackupTestCase(unittest.TestCase):
    bozp_skip_schema_guard = True

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="employee-central-413-backup-"))
        self._home_patch = patch.object(Path, "home", return_value=self.home)
        self._home_patch.start()
        import core.services.storage_service as storage_module
        import core.database.session as session_module

        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.dispose_database_engine()
        self.storage = storage_module
        self.session = session_module
        self.workspace = storage_module.storage_service.base
        self.database = storage_module.storage_service.database_path
        self.assertTrue(str(self.database).startswith(str(self.home)))
        session_module.reconfigure_database_engine(force=True)
        from core.database.database_initializer import initialize_database

        initialize_database()
        _downgrade_employee_tables(self.database)
        state = self.workspace / "konfigurace" / "migration_state.json"
        if state.exists():
            state.unlink()

    def tearDown(self) -> None:
        self.session.dispose_database_engine()
        self._home_patch.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def _backups(self) -> list[Path]:
        return sorted((self.workspace / "zalohy").glob(f"pre-migration-{TRANSITION_ID}-*.mbbackup"))

    def test_backup_is_complete_and_migration_keeps_original_rows(self) -> None:
        self.assertTrue(needs_employee_central_413_schema(self.database))
        original_path = self.database.resolve()

        prepare_database_for_startup(
            workspace_root=self.workspace,
            database_path=self.database,
        )

        self.assertEqual(self.database.resolve(), original_path)
        self.assertTrue(self.database.is_file())
        self.assertTrue(schema_is_present(self.database))
        self.assertTrue(is_transition_complete(self.workspace, TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.workspace, TRANSITION_ID))

        backups = self._backups()
        self.assertEqual(len(backups), 1)
        report = inspect_backup_integrity(backups[0])
        self.assertTrue(report.ok, msg=getattr(report, "status", None))

        snapshot = self.home / "snapshot.db"
        _backup_database(backups[0], snapshot)
        connection = sqlite3.connect(f"file:{snapshot.resolve()}?mode=ro", uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            self.assertEqual(integrity, "ok")
            self.assertNotIn("personal_number", _column_names(snapshot, "thp_workers"))
            self.assertEqual(
                connection.execute(
                    "SELECT first_name, last_name, position FROM thp_workers WHERE id = 7"
                ).fetchone(),
                ("Petr", "Starý", "Vedoucí"),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT employee_display_name FROM test_exams WHERE id = 11"
                ).fetchone()[0],
                "Bc. Jana Malá",
            )
            self.assertEqual(
                connection.execute(
                    "SELECT personal_number FROM test_employees WHERE id = 3"
                ).fetchone()[0],
                "TE-413",
            )
        finally:
            connection.close()

        self.assertIn("personal_number", _column_names(self.database, "thp_workers"))
        self.assertEqual(
            _cell(
                self.database,
                "SELECT first_name || ' ' || last_name FROM thp_workers WHERE id = 7",
            ),
            "Petr Starý",
        )
        self.assertEqual(
            _cell(self.database, "SELECT is_thp FROM thp_workers WHERE id = 7"),
            1,
        )
        self.assertEqual(
            _cell(
                self.database,
                "SELECT employee_display_name, employee_source FROM test_exams WHERE id = 11",
            ),
            "Bc. Jana Malá",
        )
        self.assertEqual(
            _cell(self.database, "SELECT employee_source FROM test_exams WHERE id = 11"),
            "test_employee",
        )
        self.assertEqual(
            _cell(self.database, "SELECT personal_number FROM test_employees WHERE id = 3"),
            "TE-413",
        )
        self.assertEqual(
            _cell(self.database, "SELECT COUNT(*) FROM test_employee_central_links"),
            0,
        )

    def test_second_start_does_not_create_another_backup(self) -> None:
        prepare_database_for_startup(
            workspace_root=self.workspace,
            database_path=self.database,
        )
        backups = self._backups()
        self.assertEqual(len(backups), 1)
        fingerprint = (backups[0].stat().st_ino, _sha256(backups[0]))

        prepare_database_for_startup(
            workspace_root=self.workspace,
            database_path=self.database,
        )

        again = self._backups()
        self.assertEqual(again, backups)
        self.assertEqual((again[0].stat().st_ino, _sha256(again[0])), fingerprint)
        self.assertFalse(needs_employee_central_413_schema(self.database))

    def test_failed_backup_does_not_migrate_or_change_database(self) -> None:
        from moduly.nastaveni.sluzby.employee_central_413_schema_migration import (
            guard_employee_central_413_migration,
        )

        before = _sha256(self.database)
        migrated = False

        def migrate() -> None:
            nonlocal migrated
            migrated = True

        with patch(
            "moduly.nastaveni.sluzby.employee_central_413_schema_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("disk je plný"),
        ):
            with self.assertRaises(PreMigrationBackupError) as caught:
                guard_employee_central_413_migration(
                    workspace_root=self.workspace,
                    database_path=self.database,
                    settings_path=None,
                    migrate=migrate,
                )

        message = str(caught.exception)
        self.assertIn("4.1.3", message)
        self.assertIn("beze změny", message)
        self.assertFalse(migrated)
        self.assertEqual(_sha256(self.database), before)
        self.assertNotIn("personal_number", _column_names(self.database, "thp_workers"))
        self.assertNotIn("employee_source", _column_names(self.database, "test_exams"))
        self.assertEqual(self._backups(), [])
        self.assertFalse(is_migration_in_progress(self.workspace, TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.workspace, TRANSITION_ID))
        self.assertEqual(
            _cell(self.database, "SELECT last_name FROM thp_workers WHERE id = 7"),
            "Starý",
        )

    def test_unfinished_migration_is_not_retried_and_backup_stays(self) -> None:
        prepare_database_for_startup(
            workspace_root=self.workspace,
            database_path=self.database,
        )
        backup = self._backups()[0]
        fingerprint = _sha256(backup)
        from core.database.upgrade_guard import write_migration_state

        write_migration_state(
            self.workspace,
            {
                "completed_transitions": [],
                "in_progress": {
                    "transition_id": TRANSITION_ID,
                    "pre_migration_backup": str(backup),
                },
            },
        )
        before = _sha256(self.database)

        with self.assertRaises(Exception) as caught:
            prepare_database_for_startup(
                workspace_root=self.workspace,
                database_path=self.database,
            )

        self.assertIn("dokončen", str(caught.exception))
        self.assertEqual(self._backups(), [backup])
        self.assertEqual(_sha256(backup), fingerprint)
        self.assertEqual(_sha256(self.database), before)
