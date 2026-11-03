"""Sloupec tasks.source_module a předmigrační záloha 4.1.3 → 4.2.0."""

from __future__ import annotations

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
    RELEASE_420_TRANSITION_ID,
    is_migration_in_progress,
    is_transition_complete,
    needs_release_420_schema,
    prepare_database_for_startup,
)


def _columns(path: Path, table: str) -> set[str]:
    connection = sqlite3.connect(str(path))
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    finally:
        connection.close()


class TaskSourceColumnTestCase(unittest.TestCase):
    bozp_skip_schema_guard = True

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="task-source-column-"))
        self._home_patch = patch.object(Path, "home", return_value=self.home)
        self._home_patch.start()
        import core.services.storage_service as storage_module
        import core.database.session as session_module

        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.dispose_database_engine()
        self.session = session_module
        self.database = storage_module.storage_service.database_path
        self.database.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.session.dispose_database_engine()
        self._home_patch.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def _legacy_tasks(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute(
                """
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(250) NOT NULL,
                    description TEXT DEFAULT '',
                    status VARCHAR(50) DEFAULT 'open',
                    completed BOOLEAN DEFAULT 0,
                    due_date DATE,
                    workplace_id INTEGER,
                    workplace_name VARCHAR(150) DEFAULT ''
                )
                """
            )
            connection.execute(
                "INSERT INTO tasks(id, title, status, workplace_id, workplace_name) "
                "VALUES (4, ?, ?, ?, ?)",
                ("Úkol BOZP 3.1.0", "open", 9, "Provozní hala"),
            )
            connection.commit()
        finally:
            connection.close()

    def test_missing_source_module_is_added_without_rewriting_the_task(self) -> None:
        self._legacy_tasks()
        self.session.reconfigure_database_engine(force=True)
        from core.database.database_initializer import _ensure_task_columns

        _ensure_task_columns()
        _ensure_task_columns()

        self.assertIn("source_module", _columns(self.database, "tasks"))
        self.assertIn("source_record_id", _columns(self.database, "tasks"))
        connection = sqlite3.connect(str(self.database))
        try:
            rows = connection.execute(
                "SELECT id, title, status, workplace_id, workplace_name, "
                "source_module, source_record_id FROM tasks"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(
            rows,
            [(4, "Úkol BOZP 3.1.0", "open", 9, "Provozní hala", "manual", None)],
        )

    def test_existing_source_module_value_is_kept(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute(
                """
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(250) NOT NULL,
                    workplace_id INTEGER,
                    source_module VARCHAR(50) NOT NULL,
                    source_record_id INTEGER
                )
                """
            )
            connection.execute(
                "INSERT INTO tasks(id, title, workplace_id, source_module, "
                "source_record_id) VALUES (8, ?, ?, ?, ?)",
                ("Navázaný úkol", 3, "audit", 15),
            )
            connection.commit()
        finally:
            connection.close()
        self.session.reconfigure_database_engine(force=True)
        from core.database.database_initializer import _ensure_task_columns

        _ensure_task_columns()

        connection = sqlite3.connect(str(self.database))
        try:
            row = connection.execute(
                "SELECT id, title, workplace_id, source_module, source_record_id "
                "FROM tasks"
            ).fetchone()
            count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(row, (8, "Navázaný úkol", 3, "audit", 15))
        self.assertEqual(count, 1)
        connection = sqlite3.connect(str(self.database))
        try:
            names = [
                str(item[1])
                for item in connection.execute("PRAGMA table_info(tasks)").fetchall()
            ]
        finally:
            connection.close()
        self.assertEqual(names.count("source_module"), 1)


class Release420BackupTestCase(unittest.TestCase):
    bozp_skip_schema_guard = True

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="release-420-backup-"))
        self._home_patch = patch.object(Path, "home", return_value=self.home)
        self._home_patch.start()
        import core.services.storage_service as storage_module
        import core.database.session as session_module

        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.dispose_database_engine()
        self.session = session_module
        self.storage = storage_module
        self.workspace = storage_module.storage_service.base
        self.database = storage_module.storage_service.database_path
        session_module.reconfigure_database_engine(force=True)
        from core.database.database_initializer import initialize_database

        initialize_database()
        self._seed_user_data()
        self._strip_release_420_schema()
        self.session.dispose_database_engine()

    def tearDown(self) -> None:
        self.session.dispose_database_engine()
        self._home_patch.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def _seed_user_data(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute(
                """
                INSERT INTO periodic_activities (
                    title, place_kind, workplace_name, place_text,
                    responsible_person_name, next_due_date, repeat_every,
                    repeat_unit, notify_every, notify_unit, next_from,
                    calendar_setup_required, note,
                    active, created_at, updated_at
                ) VALUES (
                    'Měsíční revize', 'none', '', '',
                    '', '2026-03-15', 6,
                    'months', 7, 'days', 'planned',
                    0, 'původní poznámka',
                    1, '2026-01-01 00:00:00', '2026-01-01 00:00:00'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO tasks (
                    title, description, status, priority, responsible_person,
                    workplace_name, completed, requires_verification,
                    checked_by_name, canceled, note, source_module, task_type,
                    source_check_code, created_at, updated_at
                ) VALUES (
                    'Úkol z 4.1.3', '', 'Aktivní', 'Normální', '',
                    'Hala', 0, 0,
                    '', 0, '', 'manual', 'corrective',
                    '', '2026-01-01 00:00:00', '2026-01-01 00:00:00'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO attachments (
                    entity_type, entity_id, stored_path, original_path, filename,
                    created_at
                ) VALUES ('periodic_activity', 1, ?, ?, 'protokol.txt',
                    '2026-01-01 00:00:00')
                """,
                ("periodic/1/protokol.txt", "/import/protokol.txt"),
            )
            connection.commit()
        finally:
            connection.close()
        attachment = self.workspace / "prilohy" / "periodic" / "1"
        attachment.mkdir(parents=True)
        (attachment / "protokol.txt").write_text("historicky-protokol", encoding="utf-8")
        config = self.workspace / "konfigurace"
        config.mkdir(parents=True, exist_ok=True)
        (config / "uzivatelske-nastaveni.json").write_text(
            '{"jazyk": "cs"}\n',
            encoding="utf-8",
        )
        previous = self.workspace / "zalohy" / "pre-migration-4.1.2-to-4.1.3-stara.mbbackup"
        previous.parent.mkdir(parents=True, exist_ok=True)
        previous.write_bytes(b"puvodni-zaloha")

    def _strip_release_420_schema(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            for column in (
                "calendar_start_year",
                "calendar_start_month",
                "calendar_interval_months",
                "calendar_setup_required",
            ):
                connection.execute(
                    f"ALTER TABLE periodic_activities DROP COLUMN {column}"
                )
            connection.execute("DROP TABLE IF EXISTS periodic_calendar_occurrences")
            connection.commit()
        finally:
            connection.close()
        self.assertTrue(needs_release_420_schema(self.database))

    def _backups(self) -> list[Path]:
        return sorted(
            (self.workspace / "zalohy").glob(
                f"pre-migration-{RELEASE_420_TRANSITION_ID}-*.mbbackup"
            )
        )

    def _prepare(self):
        self.session.reconfigure_database_engine(force=True)
        return prepare_database_for_startup(
            workspace_root=self.workspace,
            database_path=self.database,
        )

    def test_backup_precedes_schema_write_and_second_start_is_quiet(self) -> None:
        result = self._prepare()
        self.assertFalse(result.migrated)
        backups = self._backups()
        self.assertEqual(len(backups), 1)
        self.assertTrue(inspect_backup_integrity(backups[0]).ok)
        self.assertTrue(is_transition_complete(self.workspace, RELEASE_420_TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.workspace, RELEASE_420_TRANSITION_ID))
        with zipfile.ZipFile(backups[0]) as archive:
            names = set(archive.namelist())
            self.assertIn("database/manager_bozp.db", names)
            self.assertIn("workspace/prilohy/periodic/1/protokol.txt", names)
            self.assertEqual(
                archive.read("workspace/prilohy/periodic/1/protokol.txt"),
                "historicky-protokol".encode(),
            )
            snapshot = self.home / "snapshot.db"
            snapshot.write_bytes(archive.read("database/manager_bozp.db"))
        self.assertNotIn("calendar_start_year", _columns(snapshot, "periodic_activities"))
        self.assertFalse(needs_release_420_schema(self.database))
        connection = sqlite3.connect(str(self.database))
        try:
            periodic = connection.execute(
                "SELECT id, title, next_due_date, repeat_every, repeat_unit, "
                "next_from, note, calendar_start_year, calendar_start_month, "
                "calendar_interval_months, calendar_setup_required "
                "FROM periodic_activities"
            ).fetchone()
            task = connection.execute(
                "SELECT id, title, source_module FROM tasks"
            ).fetchone()
            attachment = connection.execute(
                "SELECT id, entity_id, stored_path, filename FROM attachments"
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(
            periodic,
            (1, "Měsíční revize", "2026-03-15", 6, "months", "planned", "původní poznámka", 2026, 3, 6, 0),
        )
        self.assertEqual(task, (1, "Úkol z 4.1.3", "manual"))
        self.assertEqual(attachment, (1, 1, "periodic/1/protokol.txt", "protokol.txt"))
        self.assertEqual(
            (self.workspace / "prilohy" / "periodic" / "1" / "protokol.txt").read_text(
                encoding="utf-8"
            ),
            "historicky-protokol",
        )
        self.assertEqual(
            (self.workspace / "zalohy" / "pre-migration-4.1.2-to-4.1.3-stara.mbbackup").read_bytes(),
            b"puvodni-zaloha",
        )

        self._prepare()
        self.assertEqual(self._backups(), backups)

    def test_failed_backup_does_not_write_the_schema(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            before = connection.execute(
                "SELECT id, title, next_due_date, repeat_every, repeat_unit, note "
                "FROM periodic_activities"
            ).fetchall()
        finally:
            connection.close()
        with patch(
            "core.database.upgrade_guard.create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("disk je plný"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                self._prepare()
        self.assertTrue(needs_release_420_schema(self.database))
        self.assertNotIn("calendar_start_year", _columns(self.database, "periodic_activities"))
        connection = sqlite3.connect(str(self.database))
        try:
            after = connection.execute(
                "SELECT id, title, next_due_date, repeat_every, repeat_unit, note "
                "FROM periodic_activities"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(after, before)
        self.assertFalse(is_migration_in_progress(self.workspace, RELEASE_420_TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.workspace, RELEASE_420_TRANSITION_ID))
        self.assertEqual(self._backups(), [])
        self.assertEqual(
            (self.workspace / "prilohy" / "periodic" / "1" / "protokol.txt").read_text(
                encoding="utf-8"
            ),
            "historicky-protokol",
        )


if __name__ == "__main__":
    unittest.main()
