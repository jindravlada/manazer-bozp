"""MIGRATION-GUARD-TRANSITION-OWNERSHIP-1: cizí in_progress nelze vymazat."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="migration-guard-ownership-1-"))
_HOME = _TMP / "home"
_HOME.mkdir(parents=True)

with patch.object(Path, "home", return_value=_HOME):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

from core.database.upgrade_guard import (  # noqa: E402
    TRANSITION_ID as LEGACY_TRANSITION_ID,
    MigrationGuardError,
    MigrationIncompleteError,
    is_migration_in_progress,
    is_transition_complete,
    mark_migration_complete,
    mark_migration_in_progress,
    migration_state_path,
    prepare_database_for_startup,
    read_migration_state,
    sqlite_table_exists,
    write_migration_state,
)
from moduly.statni_dozor.sluzby.state_supervision_core_1_schema_migration import (  # noqa: E402
    TABLE_NAME as SS_CORE1_TABLE,
    TRANSITION_ID as SS_CORE1_ID,
    prepare_state_supervision_core_1_schema,
)
from moduly.statni_dozor.sluzby.state_supervision_documents_core_2c0_schema_migration import (  # noqa: E402
    TABLE_NAME as SS_DOCUMENTS_TABLE,
    TRANSITION_ID as SS_DOCUMENTS_ID,
)
from moduly.statni_dozor.sluzby.state_supervision_participants_core_3c0_schema_migration import (  # noqa: E402
    TABLE_NAME as SS_PARTICIPANTS_TABLE,
    TRANSITION_ID as SS_PARTICIPANTS_ID,
)
from moduly.statni_dozor.sluzby.state_supervision_timeline_core_3a0_schema_migration import (  # noqa: E402
    TABLE_NAME as SS_TIMELINE_TABLE,
    TRANSITION_ID as SS_TIMELINE_ID,
)

_FAKE_BACKUP = Path("/tmp/pre_migration_guard_ownership_fake.mbbackup")
_FOREIGN_ID = "foreign-transition-for-ownership-1"
_UNKNOWN_ID = "unknown-transition-not-in-codebase"


def _ws() -> Path:
    return Path(tempfile.mkdtemp(prefix="migration-guard-ws-"))


def _put_in_progress(workspace: Path, transition_id: str) -> dict:
    write_migration_state(workspace, {})
    mark_migration_in_progress(
        workspace,
        backup_path=_FAKE_BACKUP,
        transition_id=transition_id,
    )
    return read_migration_state(workspace)


def _state_bytes(workspace: Path) -> bytes:
    path = migration_state_path(workspace)
    return path.read_bytes() if path.is_file() else b""


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


class MarkMigrationCompleteOwnershipTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = _ws()

    def test_complete_without_in_progress_adds_completed(self) -> None:
        mark_migration_complete(
            self.ws, backup_path=None, transition_id=SS_CORE1_ID
        )
        state = read_migration_state(self.ws)
        self.assertIsNone(state.get("in_progress"))
        self.assertIn(SS_CORE1_ID, state.get("completed_transitions") or [])
        self.assertEqual(state["last_completed"]["transition_id"], SS_CORE1_ID)

    def test_own_in_progress_is_cleared(self) -> None:
        before = _put_in_progress(self.ws, SS_CORE1_ID)
        self.assertEqual(before["in_progress"]["transition_id"], SS_CORE1_ID)
        mark_migration_complete(
            self.ws, backup_path=_FAKE_BACKUP, transition_id=SS_CORE1_ID
        )
        state = read_migration_state(self.ws)
        self.assertIsNone(state.get("in_progress"))
        self.assertIn(SS_CORE1_ID, state.get("completed_transitions") or [])
        self.assertFalse(is_migration_in_progress(self.ws, SS_CORE1_ID))

    def test_foreign_in_progress_raises_and_leaves_marker(self) -> None:
        before = _put_in_progress(self.ws, SS_CORE1_ID)
        raw_before = _state_bytes(self.ws)
        mtime_before = migration_state_path(self.ws).stat().st_mtime_ns
        with self.assertRaises(MigrationGuardError) as ctx:
            mark_migration_complete(
                self.ws,
                backup_path=None,
                transition_id=LEGACY_TRANSITION_ID,
            )
        message = str(ctx.exception)
        self.assertIn(LEGACY_TRANSITION_ID, message)
        self.assertIn(SS_CORE1_ID, message)
        self.assertIn("Dokončovaný přechod", message)
        self.assertIn("Vlastník aktivního in_progress", message)
        self.assertEqual(_state_bytes(self.ws), raw_before)
        self.assertEqual(
            migration_state_path(self.ws).stat().st_mtime_ns, mtime_before
        )
        after = read_migration_state(self.ws)
        self.assertEqual(after.get("in_progress"), before.get("in_progress"))
        self.assertNotIn(
            LEGACY_TRANSITION_ID, after.get("completed_transitions") or []
        )
        self.assertNotIn(SS_CORE1_ID, after.get("completed_transitions") or [])

    def test_in_progress_without_transition_id_blocks_complete(self) -> None:
        write_migration_state(
            self.ws,
            {
                "in_progress": {
                    "started_at": "2026-09-01T12:00:00",
                    "pre_migration_backup": str(_FAKE_BACKUP),
                }
            },
        )
        raw_before = _state_bytes(self.ws)
        with self.assertRaises(MigrationGuardError) as ctx:
            mark_migration_complete(
                self.ws, backup_path=None, transition_id=SS_CORE1_ID
            )
        self.assertIn(SS_CORE1_ID, str(ctx.exception))
        self.assertIn("chybí transition_id", str(ctx.exception))
        self.assertEqual(_state_bytes(self.ws), raw_before)
        self.assertNotIn(
            SS_CORE1_ID,
            read_migration_state(self.ws).get("completed_transitions") or [],
        )

    def test_invalid_in_progress_type_blocks_complete(self) -> None:
        write_migration_state(self.ws, {"in_progress": "poškozený-marker"})
        raw_before = _state_bytes(self.ws)
        with self.assertRaises(MigrationGuardError):
            mark_migration_complete(
                self.ws, backup_path=None, transition_id=SS_CORE1_ID
            )
        self.assertEqual(_state_bytes(self.ws), raw_before)

    def test_cannot_overwrite_foreign_in_progress(self) -> None:
        _put_in_progress(self.ws, SS_CORE1_ID)
        raw_before = _state_bytes(self.ws)
        with self.assertRaises(MigrationGuardError) as ctx:
            mark_migration_in_progress(
                self.ws,
                backup_path=_FAKE_BACKUP,
                transition_id=SS_DOCUMENTS_ID,
            )
        self.assertIn(SS_DOCUMENTS_ID, str(ctx.exception))
        self.assertIn(SS_CORE1_ID, str(ctx.exception))
        self.assertEqual(_state_bytes(self.ws), raw_before)


class StartupInProgressOwnershipTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ws = storage_module.storage_service.base
        cls.db = storage_module.storage_service.database_path
        cls.assert_tables = (
            (SS_CORE1_ID, SS_CORE1_TABLE),
            (SS_DOCUMENTS_ID, SS_DOCUMENTS_TABLE),
            (SS_TIMELINE_ID, SS_TIMELINE_TABLE),
            (SS_PARTICIPANTS_ID, SS_PARTICIPANTS_TABLE),
        )
        for _transition_id, table in cls.assert_tables:
            if not sqlite_table_exists(cls.db, table):
                raise AssertionError(f"očekávaná tabulka chybí: {table}")

    def setUp(self) -> None:
        write_migration_state(self.ws, {})
        conn = sqlite3.connect(str(self.db))
        try:
            self._supervision_count = int(
                conn.execute(f'SELECT COUNT(*) FROM "{SS_CORE1_TABLE}"').fetchone()[0]
            )
        finally:
            conn.close()

    def tearDown(self) -> None:
        write_migration_state(self.ws, {})

    def _block_startup(self, transition_id: str) -> str:
        mark_migration_in_progress(
            self.ws,
            backup_path=_FAKE_BACKUP,
            transition_id=transition_id,
        )
        before = read_migration_state(self.ws)
        raw_before = _state_bytes(self.ws)
        mtime_before = migration_state_path(self.ws).stat().st_mtime_ns
        with self.assertRaises(MigrationIncompleteError) as ctx:
            prepare_database_for_startup(
                workspace_root=self.ws, database_path=self.db
            )
        after = read_migration_state(self.ws)
        self.assertEqual(after.get("in_progress"), before.get("in_progress"))
        self.assertEqual(after.get("completed_transitions") or [], [])
        self.assertEqual(_state_bytes(self.ws), raw_before)
        self.assertEqual(
            migration_state_path(self.ws).stat().st_mtime_ns, mtime_before
        )
        self.assertEqual(_count(self.db, SS_CORE1_TABLE), self._supervision_count)
        self.assertIn(transition_id, str(ctx.exception))
        return str(ctx.exception)

    def test_ss_core1_in_progress_with_table_blocks_startup(self) -> None:
        self.assertTrue(sqlite_table_exists(self.db, SS_CORE1_TABLE))
        mark_migration_in_progress(
            self.ws,
            backup_path=_FAKE_BACKUP,
            transition_id=SS_CORE1_ID,
        )
        with self.assertRaises(MigrationGuardError) as direct:
            prepare_state_supervision_core_1_schema(
                workspace_root=self.ws, database_path=self.db
            )
        self.assertIn("nebyla dokončena", str(direct.exception))
        self.assertEqual(
            read_migration_state(self.ws)["in_progress"]["transition_id"],
            SS_CORE1_ID,
        )
        raw_before = _state_bytes(self.ws)
        with self.assertRaises(MigrationIncompleteError) as startup:
            prepare_database_for_startup(
                workspace_root=self.ws, database_path=self.db
            )
        self.assertIn(SS_CORE1_ID, str(startup.exception))
        self.assertEqual(_state_bytes(self.ws), raw_before)
        self.assertEqual(_count(self.db, SS_CORE1_TABLE), self._supervision_count)

    def test_ss_documents_in_progress_with_table_blocks_startup(self) -> None:
        self.assertTrue(sqlite_table_exists(self.db, SS_DOCUMENTS_TABLE))
        self._block_startup(SS_DOCUMENTS_ID)

    def test_ss_timeline_in_progress_with_table_blocks_startup(self) -> None:
        self.assertTrue(sqlite_table_exists(self.db, SS_TIMELINE_TABLE))
        self._block_startup(SS_TIMELINE_ID)

    def test_ss_participants_in_progress_with_table_blocks_startup(self) -> None:
        self.assertTrue(sqlite_table_exists(self.db, SS_PARTICIPANTS_TABLE))
        self._block_startup(SS_PARTICIPANTS_ID)

    def test_unknown_in_progress_blocks_startup(self) -> None:
        self._block_startup(_UNKNOWN_ID)

    def test_legacy_in_progress_still_blocks_startup(self) -> None:
        self._block_startup(LEGACY_TRANSITION_ID)

    def test_foreign_complete_cannot_clear_ss_marker(self) -> None:
        _put_in_progress(self.ws, SS_CORE1_ID)
        with self.assertRaises(MigrationGuardError):
            mark_migration_complete(
                self.ws, backup_path=None, transition_id=_FOREIGN_ID
            )
        state = read_migration_state(self.ws)
        self.assertEqual(state["in_progress"]["transition_id"], SS_CORE1_ID)
        self.assertNotIn(_FOREIGN_ID, state.get("completed_transitions") or [])

    def test_schema_present_without_in_progress_starts(self) -> None:
        result = prepare_database_for_startup(
            workspace_root=self.ws, database_path=self.db
        )
        self.assertFalse(result.migrated)
        self.assertIsNone(read_migration_state(self.ws).get("in_progress"))
        self.assertTrue(is_transition_complete(self.ws, SS_CORE1_ID))
        self.assertTrue(is_transition_complete(self.ws, LEGACY_TRANSITION_ID))

    def test_second_start_is_idempotent_and_does_not_rerun_ss(self) -> None:
        first = prepare_database_for_startup(
            workspace_root=self.ws, database_path=self.db
        )
        completed = list(
            read_migration_state(self.ws).get("completed_transitions") or []
        )
        self.assertIn(SS_CORE1_ID, completed)
        second = prepare_database_for_startup(
            workspace_root=self.ws, database_path=self.db
        )
        self.assertFalse(first.migrated)
        self.assertFalse(second.migrated)
        after = read_migration_state(self.ws)
        self.assertEqual(after.get("completed_transitions") or [], completed)
        self.assertIsNone(after.get("in_progress"))

    def test_own_marker_can_complete_then_startup(self) -> None:
        mark_migration_in_progress(
            self.ws, backup_path=_FAKE_BACKUP, transition_id=SS_CORE1_ID
        )
        mark_migration_complete(
            self.ws, backup_path=_FAKE_BACKUP, transition_id=SS_CORE1_ID
        )
        self.assertTrue(is_transition_complete(self.ws, SS_CORE1_ID))
        self.assertFalse(is_migration_in_progress(self.ws, SS_CORE1_ID))
        prepare_database_for_startup(workspace_root=self.ws, database_path=self.db)
        self.assertTrue(is_transition_complete(self.ws, SS_CORE1_ID))

    def test_corrupt_json_keeps_existing_read_convention(self) -> None:
        path = migration_state_path(self.ws)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        self.assertEqual(read_migration_state(self.ws), {})
        prepare_database_for_startup(workspace_root=self.ws, database_path=self.db)


if __name__ == "__main__":
    unittest.main()
