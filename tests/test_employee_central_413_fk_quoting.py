"""Migrace 4.1.3 má unést holé i uvozené názvy v definici zkoušek."""

from __future__ import annotations

import hashlib
import importlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.database.upgrade_guard import (
    MigrationGuardError,
    is_migration_in_progress,
    is_transition_complete,
)
from moduly.nastaveni.sluzby.employee_central_413_schema_migration import (
    TRANSITION_ID,
    guard_employee_central_413_migration,
    needs_employee_central_413_schema,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _exam_sql(style: str) -> str:
    columns = {
        "bare": (
            "id INTEGER PRIMARY KEY",
            "employee_id INTEGER NOT NULL",
            "employee_source VARCHAR(20) NOT NULL DEFAULT 'test_employee'",
            "test_definition_id INTEGER NOT NULL",
            "employee_display_name VARCHAR(300) NOT NULL",
            "note TEXT DEFAULT 'a, b'",
            "status VARCHAR(20) NOT NULL",
        ),
        "quoted_column": (
            "id INTEGER PRIMARY KEY",
            '"employee_id" INTEGER NOT NULL',
            "employee_source VARCHAR(20) NOT NULL DEFAULT 'test_employee'",
            '"test_definition_id" INTEGER NOT NULL',
            "employee_display_name VARCHAR(300) NOT NULL",
            "note TEXT DEFAULT 'a, b'",
            "status VARCHAR(20) NOT NULL",
        ),
        "quoted_all": (
            '"id" INTEGER PRIMARY KEY',
            '"employee_id" INTEGER NOT NULL',
            '"employee_source" VARCHAR(20) NOT NULL DEFAULT \'test_employee\'',
            '"test_definition_id" INTEGER NOT NULL',
            '"employee_display_name" VARCHAR(300) NOT NULL',
            '"note" TEXT DEFAULT \'a, b\'',
            '"status" VARCHAR(20) NOT NULL',
        ),
        "inline_quoted": (
            '"id" INTEGER PRIMARY KEY',
            '"employee_id" INTEGER NOT NULL REFERENCES "test_employees"("id")',
            '"employee_source" VARCHAR(20) NOT NULL DEFAULT \'test_employee\'',
            '"test_definition_id" INTEGER NOT NULL REFERENCES "test_definitions"("id")',
            '"employee_display_name" VARCHAR(300) NOT NULL',
            '"note" TEXT DEFAULT \'a, b\'',
            '"status" VARCHAR(20) NOT NULL',
        ),
        "brackets": (
            "[id] INTEGER PRIMARY KEY",
            "[employee_id] INTEGER NOT NULL",
            "[employee_source] VARCHAR(20) NOT NULL DEFAULT 'test_employee'",
            "[test_definition_id] INTEGER NOT NULL",
            "[employee_display_name] VARCHAR(300) NOT NULL",
            "[note] TEXT DEFAULT 'a, b'",
            "[status] VARCHAR(20) NOT NULL",
        ),
        "backticks": (
            "`id` INTEGER PRIMARY KEY",
            "`employee_id` INTEGER NOT NULL",
            "`employee_source` VARCHAR(20) NOT NULL DEFAULT 'test_employee'",
            "`test_definition_id` INTEGER NOT NULL",
            "`employee_display_name` VARCHAR(300) NOT NULL",
            "`note` TEXT DEFAULT 'a, b'",
            "`status` VARCHAR(20) NOT NULL",
        ),
    }
    constraints = {
        "bare": (
            "FOREIGN KEY(employee_id) REFERENCES test_employees (id)",
            "FOREIGN KEY(test_definition_id) REFERENCES test_definitions (id)",
            "CHECK (status IN ('dokonceno', 'priprava'))",
        ),
        "quoted_column": (
            'FOREIGN KEY("employee_id") REFERENCES test_employees(id)',
            'FOREIGN KEY("test_definition_id") REFERENCES test_definitions(id)',
            "CONSTRAINT ck_status CHECK (status IN ('dokonceno', 'priprava'))",
        ),
        "quoted_all": (
            'CONSTRAINT "fk_employee" FOREIGN KEY("employee_id") '
            'REFERENCES "test_employees"("id")',
            'FOREIGN KEY("test_definition_id") REFERENCES "test_definitions"("id")',
            'CONSTRAINT "ck_status" CHECK ("status" IN (\'dokonceno\', \'priprava\'))',
        ),
        "inline_quoted": (
            "CHECK (\"status\" IN ('dokonceno', 'priprava'))",
        ),
        "brackets": (
            "FOREIGN KEY([employee_id]) REFERENCES [test_employees]([id])",
            "FOREIGN KEY([test_definition_id]) REFERENCES [test_definitions]([id])",
            "CHECK ([status] IN ('dokonceno', 'priprava'))",
        ),
        "backticks": (
            "FOREIGN KEY(`employee_id`) REFERENCES `test_employees`(`id`)",
            "FOREIGN KEY(`test_definition_id`) REFERENCES `test_definitions`(`id`)",
            "CHECK (`status` IN ('dokonceno', 'priprava'))",
        ),
    }
    table = {
        "quoted_all": '"test_exams"',
        "inline_quoted": '"test_exams"',
        "brackets": "[test_exams]",
        "backticks": "`test_exams`",
    }.get(style, "test_exams")
    body = ",\n    ".join((*columns[style], *constraints[style]))
    return f"CREATE TABLE {table} (\n    {body}\n)"


class EmployeeCentral413FkQuotingTestCase(unittest.TestCase):
    bozp_skip_schema_guard = True

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="employee-central-413-fk-"))
        self._home_patch = patch.object(Path, "home", return_value=self.home)
        self._home_patch.start()
        import core.services.storage_service as storage_module
        import core.database.session as session_module

        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.dispose_database_engine()
        self.session = session_module
        self.workspace = storage_module.storage_service.base
        self.database = storage_module.storage_service.database_path
        self.assertTrue(str(self.database).startswith(str(self.home)))
        session_module.reconfigure_database_engine(force=True)
        from core.database import database_initializer

        self.initializer = database_initializer

    def tearDown(self) -> None:
        self.session.dispose_database_engine()
        self._home_patch.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def _write_exam_database(self, style: str) -> None:
        if self.database.exists():
            self.database.unlink()
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute(
                "CREATE TABLE test_employees (id INTEGER PRIMARY KEY, personal_number VARCHAR(50))"
            )
            connection.execute(
                "CREATE TABLE test_definitions (id INTEGER PRIMARY KEY, name VARCHAR(200))"
            )
            connection.execute(
                """
                CREATE TABLE test_employee_central_links (
                    id INTEGER PRIMARY KEY,
                    test_employee_id INTEGER,
                    thp_worker_id INTEGER
                )
                """
            )
            connection.execute(
                "INSERT INTO test_employees (id, personal_number) VALUES (3, 'TE-413')"
            )
            connection.execute(
                "INSERT INTO test_definitions (id, name) VALUES (1, 'Periodické přezkoušení')"
            )
            connection.execute(_exam_sql(style))
            connection.execute(
                """
                INSERT INTO test_exams (
                    id, employee_id, employee_source, test_definition_id,
                    employee_display_name, note, status
                ) VALUES (
                    11, 3, 'test_employee', 1, 'Bc. Jana Malá', 'a, b', 'dokonceno'
                )
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.session.reconfigure_database_engine(force=True)

    def _assert_historical_exam_kept(self, style: str) -> None:
        self._write_exam_database(style)
        self.initializer._release_exam_employee_foreign_keys()
        self.initializer._release_exam_employee_foreign_keys()

        connection = sqlite3.connect(f"file:{self.database.resolve()}?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            definition = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'test_exams'"
            ).fetchone()[0]
            self.assertIn("dokonceno", definition)
            self.assertIn("priprava", definition)
            self.assertNotIn("__fkrepair", definition)
            foreign_keys = connection.execute(
                'PRAGMA foreign_key_list("test_exams")'
            ).fetchall()
            targets = {(row[3], row[2]) for row in foreign_keys}
            self.assertNotIn(("employee_id", "test_employees"), targets)
            self.assertIn(("test_definition_id", "test_definitions"), targets)
            self.assertEqual(
                connection.execute(
                    """
                    SELECT employee_display_name, note, status, employee_source
                    FROM test_exams WHERE id = 11
                    """
                ).fetchone(),
                ("Bc. Jana Malá", "a, b", "dokonceno", "test_employee"),
            )
            leftovers = connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE name LIKE '%__fkrepair%' OR name LIKE '%__kept%'
                """
            ).fetchall()
            self.assertEqual(leftovers, [])
        finally:
            connection.close()
        self.assertFalse(needs_employee_central_413_schema(self.database))

    def test_bare_names_keep_check_and_history(self) -> None:
        self._assert_historical_exam_kept("bare")

    def test_quoted_column_names_do_not_leave_broken_foreign_key(self) -> None:
        self._assert_historical_exam_kept("quoted_column")

    def test_fully_quoted_names_and_named_constraints(self) -> None:
        self._assert_historical_exam_kept("quoted_all")

    def test_inline_quoted_references_keep_the_other_foreign_key(self) -> None:
        self._assert_historical_exam_kept("inline_quoted")

    def test_bracket_identifiers(self) -> None:
        self._assert_historical_exam_kept("brackets")

    def test_backtick_identifiers(self) -> None:
        self._assert_historical_exam_kept("backticks")

    def test_guard_keeps_one_backup_after_quoted_migration(self) -> None:
        self._write_exam_database("quoted_column")

        backup = guard_employee_central_413_migration(
            workspace_root=self.workspace,
            database_path=self.database,
            settings_path=None,
            migrate=self.initializer._release_exam_employee_foreign_keys,
        )

        self.assertIsNotNone(backup)
        backups = sorted(
            (self.workspace / "zalohy").glob(f"pre-migration-{TRANSITION_ID}-*.mbbackup")
        )
        self.assertEqual(backups, [backup])
        fingerprint = (backup.stat().st_ino, _sha256(backup))
        self.assertTrue(is_transition_complete(self.workspace, TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.workspace, TRANSITION_ID))

        again = guard_employee_central_413_migration(
            workspace_root=self.workspace,
            database_path=self.database,
            settings_path=None,
            migrate=self.initializer._release_exam_employee_foreign_keys,
        )

        self.assertIsNone(again)
        self.assertEqual(
            sorted(
                (self.workspace / "zalohy").glob(
                    f"pre-migration-{TRANSITION_ID}-*.mbbackup"
                )
            ),
            [backup],
        )
        self.assertEqual((backup.stat().st_ino, _sha256(backup)), fingerprint)
        connection = sqlite3.connect(f"file:{self.database.resolve()}?mode=ro", uri=True)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT employee_display_name FROM test_exams WHERE id = 11"
                ).fetchone()[0],
                "Bc. Jana Malá",
            )
        finally:
            connection.close()

    def test_failed_migration_keeps_the_block_and_the_backup(self) -> None:
        self._write_exam_database("quoted_all")
        before = _sha256(self.database)

        def migrate() -> None:
            raise RuntimeError("selhání zápisu tabulky test_exams__fkrepair")

        with self.assertRaises(MigrationGuardError) as caught:
            guard_employee_central_413_migration(
                workspace_root=self.workspace,
                database_path=self.database,
                settings_path=None,
                migrate=migrate,
            )

        self.assertIn("4.1.3", str(caught.exception))
        self.assertTrue(is_migration_in_progress(self.workspace, TRANSITION_ID))
        backups = sorted(
            (self.workspace / "zalohy").glob(f"pre-migration-{TRANSITION_ID}-*.mbbackup")
        )
        self.assertEqual(len(backups), 1)
        fingerprint = _sha256(backups[0])
        self.assertEqual(_sha256(self.database), before)

        def must_not_run() -> None:
            raise AssertionError("další migrace se nesmí spustit")

        with self.assertRaises(MigrationGuardError) as blocked:
            guard_employee_central_413_migration(
                workspace_root=self.workspace,
                database_path=self.database,
                settings_path=None,
                migrate=must_not_run,
            )

        self.assertIn("nebyla dokončena", str(blocked.exception))
        self.assertEqual(_sha256(backups[0]), fingerprint)
        self.assertEqual(
            sorted(
                (self.workspace / "zalohy").glob(
                    f"pre-migration-{TRANSITION_ID}-*.mbbackup"
                )
            ),
            backups,
        )
        self.assertEqual(_sha256(self.database), before)
