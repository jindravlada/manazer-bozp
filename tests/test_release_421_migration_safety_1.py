"""Předmigrační záloha 4.2.0 → 4.2.1: rizika dodavatelů a vznik MU."""

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
    MigrationGuardError,
    PreMigrationBackupError,
    RELEASE_420_TRANSITION_ID,
    RELEASE_421_TRANSITION_ID,
    is_migration_in_progress,
    is_transition_complete,
    needs_release_421_schema,
    prepare_database_for_startup,
    write_migration_state,
)

_SUPPLIER_TABLES = (
    "coordination_risk_receipt_history",
    "coordination_risk_receipts",
    "coordination_supplier_risk_links",
    "supplier_risk_documents",
    "supplier_risk_companies",
)


def _columns(path: Path, table: str) -> set[str]:
    connection = sqlite3.connect(str(path))
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    finally:
        connection.close()


def _tables(path: Path) -> set[str]:
    connection = sqlite3.connect(str(path))
    try:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        connection.close()


class Release421BackupTestCase(unittest.TestCase):
    bozp_skip_schema_guard = True

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="release-421-backup-"))
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
        session_module.reconfigure_database_engine(force=True)
        from core.database.database_initializer import initialize_database

        initialize_database()
        self.session.dispose_database_engine()

    def tearDown(self) -> None:
        self.session.dispose_database_engine()
        self._home_patch.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def _prepare(self):
        self.session.reconfigure_database_engine(force=True)
        return prepare_database_for_startup(
            workspace_root=self.workspace,
            database_path=self.database,
        )

    def _backups(self, transition_id: str) -> list[Path]:
        return sorted((self.workspace / "zalohy").glob(f"pre-migration-{transition_id}-*.mbbackup"))

    def _snapshot(self, backup: Path) -> Path:
        target = self.home / f"snapshot-{backup.stem}.db"
        with zipfile.ZipFile(backup) as archive:
            target.write_bytes(archive.read("database/manager_bozp.db"))
        return target

    def _insert_investigation(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            info = connection.execute("PRAGMA table_info(mu_investigations)").fetchall()
            names: list[str] = []
            params: list[str] = []
            for _cid, name, _coltype, notnull, _default, _pk in info:
                if name in {"id", "event_date", "event_time"}:
                    continue
                names.append(name)
                if name == "number":
                    params.append("MU-7")
                elif name == "title":
                    params.append("Pád břemene")
                elif name == "short_description":
                    params.append("původní popis")
                elif name in {"created_at", "updated_at"}:
                    params.append("2026-04-02 08:00:00")
                else:
                    params.append("")
            placeholders = ", ".join("?" for _ in names)
            connection.execute(
                f"INSERT INTO mu_investigations ({', '.join(names)}) VALUES ({placeholders})",
                params,
            )
            connection.commit()
        finally:
            connection.close()

    def _drop_event_columns(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute("ALTER TABLE mu_investigations DROP COLUMN event_time")
            connection.execute("ALTER TABLE mu_investigations DROP COLUMN event_date")
            connection.commit()
        finally:
            connection.close()

    def _drop_supplier_tables(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            for name in _SUPPLIER_TABLES:
                connection.execute(f"DROP TABLE IF EXISTS {name}")
            connection.commit()
        finally:
            connection.close()

    def _investigation(self) -> tuple:
        connection = sqlite3.connect(str(self.database))
        try:
            return connection.execute(
                "SELECT number, title, short_description, event_date, event_time "
                "FROM mu_investigations"
            ).fetchone()
        finally:
            connection.close()

    def test_public_420_is_backed_up_before_tables_and_columns(self) -> None:
        self._drop_supplier_tables()
        self._drop_event_columns()
        self._insert_investigation()
        self.assertTrue(needs_release_421_schema(self.database))

        self._prepare()

        backups = self._backups(RELEASE_421_TRANSITION_ID)
        self.assertEqual(len(backups), 1)
        self.assertEqual(self._backups(RELEASE_420_TRANSITION_ID), [])
        self.assertTrue(inspect_backup_integrity(backups[0]).ok)
        self.assertTrue(is_transition_complete(self.workspace, RELEASE_421_TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.workspace, RELEASE_421_TRANSITION_ID))
        snapshot = self._snapshot(backups[0])
        self.assertTrue(needs_release_421_schema(snapshot))
        self.assertNotIn("supplier_risk_companies", _tables(snapshot))
        self.assertNotIn("event_date", _columns(snapshot, "mu_investigations"))
        self.assertFalse(needs_release_421_schema(self.database))
        self.assertIn("supplier_risk_companies", _tables(self.database))
        self.assertIn("coordination_risk_receipt_history", _tables(self.database))
        self.assertEqual(
            self._investigation(),
            ("MU-7", "Pád břemene", "původní popis", None, None),
        )

        self._prepare()
        self.assertEqual(self._backups(RELEASE_421_TRANSITION_ID), backups)

    def test_internal_421_with_tables_still_backs_up_missing_columns(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute(
                """
                INSERT INTO supplier_risk_companies (name, ico, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                ("Dodavatel Alfa", "12345678", "2026-04-02 08:00:00", "2026-04-02 08:00:00"),
            )
            connection.commit()
        finally:
            connection.close()
        self._drop_event_columns()
        self._insert_investigation()
        self.assertTrue(needs_release_421_schema(self.database))
        self.assertIn("supplier_risk_companies", _tables(self.database))

        self._prepare()

        backups = self._backups(RELEASE_421_TRANSITION_ID)
        self.assertEqual(len(backups), 1)
        snapshot = self._snapshot(backups[0])
        self.assertIn("supplier_risk_companies", _tables(snapshot))
        self.assertNotIn("event_date", _columns(snapshot, "mu_investigations"))
        self.assertNotIn("event_time", _columns(snapshot, "mu_investigations"))
        self.assertFalse(needs_release_421_schema(self.database))
        self.assertEqual(
            self._investigation(),
            ("MU-7", "Pád břemene", "původní popis", None, None),
        )
        connection = sqlite3.connect(str(self.database))
        try:
            company = connection.execute(
                "SELECT name, ico FROM supplier_risk_companies"
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(company, ("Dodavatel Alfa", "12345678"))

        self._prepare()
        self.assertEqual(self._backups(RELEASE_421_TRANSITION_ID), backups)

    def test_failed_backup_does_not_change_the_schema(self) -> None:
        self._drop_supplier_tables()
        self._drop_event_columns()
        self._insert_investigation()
        with patch(
            "core.database.upgrade_guard.create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("disk je plný"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                self._prepare()
        self.assertTrue(needs_release_421_schema(self.database))
        self.assertNotIn("supplier_risk_companies", _tables(self.database))
        self.assertNotIn("event_date", _columns(self.database, "mu_investigations"))
        connection = sqlite3.connect(str(self.database))
        try:
            row = connection.execute(
                "SELECT number, title, short_description FROM mu_investigations"
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row, ("MU-7", "Pád břemene", "původní popis"))
        self.assertFalse(is_migration_in_progress(self.workspace, RELEASE_421_TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.workspace, RELEASE_421_TRANSITION_ID))
        self.assertEqual(self._backups(RELEASE_421_TRANSITION_ID), [])

    def test_interrupted_transition_does_not_continue_or_add_backup(self) -> None:
        self._drop_event_columns()
        self._insert_investigation()
        backup = self.workspace / "zalohy" / (
            f"pre-migration-{RELEASE_421_TRANSITION_ID}-preruseno.mbbackup"
        )
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(b"puvodni-zaloha")
        write_migration_state(
            self.workspace,
            {
                "in_progress": {
                    "transition_id": RELEASE_421_TRANSITION_ID,
                    "started_at": "2026-11-09T10:00:00",
                    "pre_migration_backup": str(backup),
                },
                "completed_transitions": [],
            },
        )
        with self.assertRaises(MigrationGuardError):
            self._prepare()
        self.assertTrue(needs_release_421_schema(self.database))
        self.assertNotIn("event_date", _columns(self.database, "mu_investigations"))
        self.assertEqual(self._backups(RELEASE_421_TRANSITION_ID), [backup])
        self.assertEqual(backup.read_bytes(), b"puvodni-zaloha")
        self.assertTrue(is_migration_in_progress(self.workspace, RELEASE_421_TRANSITION_ID))

    def test_current_schema_does_not_create_backup(self) -> None:
        self._insert_investigation()
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute(
                "UPDATE mu_investigations SET event_date = ?, event_time = ? WHERE number = ?",
                ("2026-04-02", "08:15", "MU-7"),
            )
            connection.commit()
        finally:
            connection.close()
        self.assertFalse(needs_release_421_schema(self.database))

        self._prepare()
        self._prepare()

        self.assertEqual(self._backups(RELEASE_421_TRANSITION_ID), [])
        self.assertEqual(
            self._investigation(),
            ("MU-7", "Pád břemene", "původní popis", "2026-04-02", "08:15"),
        )


if __name__ == "__main__":
    unittest.main()
