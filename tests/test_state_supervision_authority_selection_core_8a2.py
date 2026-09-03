"""STATE-SUPERVISION-AUTHORITY-SELECTION-CORE-8A2: snapshot orgánu a pracoviště."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SUPERVISIONS_TABLE = "state_supervisions"
AUTHORITIES_TABLE = "control_authorities"
OFFICES_TABLE = "control_authority_offices"


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _tables(db_path: Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
    finally:
        conn.close()


def _indexes(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {
            str(row[1])
            for row in conn.execute(f'PRAGMA index_list("{table}")').fetchall()
        }
    finally:
        conn.close()


def _columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {
            str(row[1])
            for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        }
    finally:
        conn.close()


def _supervision_row(db_path: Path) -> tuple:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            """
            SELECT authority_name, authority_address, authority_ico,
                   authority_office_id, status, workplace_name_snapshot
            FROM state_supervisions
            """
        ).fetchone()
    finally:
        conn.close()


def _catalog_stamps(db_path: Path) -> tuple[list, list]:
    conn = sqlite3.connect(str(db_path))
    try:
        authorities = conn.execute(
            "SELECT id, code, name, origin, user_edited_at, external_key "
            "FROM control_authorities ORDER BY id"
        ).fetchall()
        offices = conn.execute(
            "SELECT id, authority_id, name, origin, user_edited_at, external_key "
            "FROM control_authority_offices ORDER BY id"
        ).fetchall()
        return list(authorities), list(offices)
    finally:
        conn.close()


def _seed_pre_8a2_db(db_path: Path) -> None:
    """DB po CORE-1 + 8A0, bez authority_id a office name snapshotu."""
    from moduly.statni_dozor.sluzby.state_supervision_authority_catalog_core_8a0_schema_migration import (
        apply_state_supervision_authority_catalog_core_8a0_schema_ddl,
    )
    from moduly.statni_dozor.sluzby.state_supervision_core_1_schema_migration import (
        DDL_STATEMENTS as CORE1_DDL,
    )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            side.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        for statement in CORE1_DDL:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()

    apply_state_supervision_authority_catalog_core_8a0_schema_ddl(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO state_supervisions (
                status, authority_ico, authority_name, authority_address,
                authority_office_id,
                workplace_name_snapshot, workplace_address_snapshot,
                power_of_attorney_required, created_at, updated_at
            ) VALUES (
                'announced', '12345678', 'OIP Praha', 'Kladenská 1',
                NULL,
                'Provoz A', 'Ulice 1',
                0, '2026-03-01 09:00:00', '2026-03-01 09:00:00'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO control_authorities (
                code, name, active, display_order, origin, external_key,
                user_edited_at, created_at, updated_at
            ) VALUES (
                'suip-legacy', 'SÚIP', 1, 0, 'bundled', 'suip:legacy',
                '2026-02-01 10:00:00', '2026-02-01 10:00:00', '2026-02-01 10:00:00'
            )
            """
        )
        authority_id = conn.execute(
            "SELECT id FROM control_authorities WHERE code = 'suip-legacy'"
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO control_authority_offices (
                authority_id, name, active, display_order, origin, external_key,
                user_edited_at, created_at, updated_at
            ) VALUES (
                ?, 'OIP Praha', 1, 0, 'bundled', 'suip:oip-praha-legacy',
                '2026-02-01 10:00:00', '2026-02-01 10:00:00', '2026-02-01 10:00:00'
            )
            """,
            (authority_id,),
        )
        conn.commit()
    finally:
        conn.close()


_MIG_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-selection-8a2-mig-"))
_MIG_HOME_PATCHER = patch.object(Path, "home", return_value=_MIG_HOME)
_MIG_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)

from core.database.upgrade_guard import (  # noqa: E402
    MigrationGuardError,
    PreMigrationBackupError,
    is_migration_failed,
    is_transition_complete,
    mark_migration_complete,
    mark_migration_in_progress,
    prepare_database_for_startup,
    read_migration_state,
    write_migration_state,
)
from moduly.statni_dozor.sluzby.state_supervision_authority_catalog_core_8a0_schema_migration import (  # noqa: E402
    TRANSITION_ID as CATALOG_8A0_TRANSITION_ID,
)
from moduly.statni_dozor.sluzby.state_supervision_authority_selection_core_8a2_schema_migration import (  # noqa: E402
    AUTHORITY_ID_COLUMN,
    AUTHORITY_ID_INDEX,
    AUTHORITY_OFFICE_ID_INDEX,
    BACKUP_NAME_PREFIX,
    OFFICE_NAME_SNAPSHOT_COLUMN,
    TRANSITION_ID,
    allocate_state_supervision_authority_selection_core_8a2_backup_path,
    needs_state_supervision_authority_selection_core_8a2_schema,
    prepare_state_supervision_authority_selection_core_8a2_schema,
)
from moduly.statni_dozor.sluzby.state_supervision_core_1_schema_migration import (  # noqa: E402
    TRANSITION_ID as CORE1_TRANSITION_ID,
)

_MIG_HOME_PATCHER.stop()


class StateSupervisionAuthoritySelectionCore8a2MigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._home = patch.object(Path, "home", return_value=_MIG_HOME)
        self._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

        self.db_path = storage_module.storage_service.database_path
        self.ws = storage_module.storage_service.base
        state_path = self.ws / "konfigurace" / "migration_state.json"
        if state_path.exists():
            state_path.unlink()
        for backup in (self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"):
            backup.unlink()
        _seed_pre_8a2_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_01_backup_before_ddl(self) -> None:
        result = prepare_state_supervision_authority_selection_core_8a2_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertTrue(result.migrated)
        assert result.pre_migration_backup_path is not None
        self.assertTrue(result.pre_migration_backup_path.is_file())
        self.assertTrue(
            result.pre_migration_backup_path.name.startswith(BACKUP_NAME_PREFIX)
        )
        self.assertEqual(result.pre_migration_backup_path.suffix, ".mbbackup")

    def test_02_backup_failure_no_ddl(self) -> None:
        before_columns = _columns(self.db_path, SUPERVISIONS_TABLE)
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_authority_selection_core_8a2_schema_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_state_supervision_authority_selection_core_8a2_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertEqual(_columns(self.db_path, SUPERVISIONS_TABLE), before_columns)
        self.assertNotIn(AUTHORITY_ID_COLUMN, before_columns)
        self.assertTrue(
            needs_state_supervision_authority_selection_core_8a2_schema(self.db_path)
        )

    def test_03_upgrade_adds_nullable_fields_without_backfill(self) -> None:
        before_row = _supervision_row(self.db_path)
        before_auth, before_off = _catalog_stamps(self.db_path)
        prepare_state_supervision_authority_selection_core_8a2_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        columns = _columns(self.db_path, SUPERVISIONS_TABLE)
        self.assertIn(AUTHORITY_ID_COLUMN, columns)
        self.assertIn(OFFICE_NAME_SNAPSHOT_COLUMN, columns)
        self.assertIn("authority_office_id", columns)
        indexes = _indexes(self.db_path, SUPERVISIONS_TABLE)
        self.assertIn(AUTHORITY_ID_INDEX, indexes)
        self.assertIn(AUTHORITY_OFFICE_ID_INDEX, indexes)
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT authority_id, authority_office_name_snapshot, "
                "authority_name, authority_address, authority_ico, "
                "authority_office_id FROM state_supervisions"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNone(row[0])
        self.assertIsNone(row[1])
        self.assertEqual(row[2], "OIP Praha")
        self.assertEqual(row[3], "Kladenská 1")
        self.assertEqual(row[4], "12345678")
        self.assertIsNone(row[5])
        self.assertEqual(_supervision_row(self.db_path), before_row)
        self.assertEqual(_catalog_stamps(self.db_path), (before_auth, before_off))

    def test_04_no_backfill_by_name(self) -> None:
        prepare_state_supervision_authority_selection_core_8a2_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT authority_id, authority_office_id, "
                "authority_office_name_snapshot FROM state_supervisions"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNone(row[0])
        self.assertIsNone(row[1])
        self.assertIsNone(row[2])

    def test_05_idempotent_repeat(self) -> None:
        first = prepare_state_supervision_authority_selection_core_8a2_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        backups_first = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"))
        self.assertEqual(len(backups_first), 1)
        second = prepare_state_supervision_authority_selection_core_8a2_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertFalse(second.migrated)
        backups_second = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"))
        self.assertEqual(len(backups_second), 1)
        self.assertEqual(first.pre_migration_backup_path, backups_second[0])

    def test_06_previous_markers_unchanged(self) -> None:
        mark_migration_complete(
            self.ws, backup_path=None, transition_id=CORE1_TRANSITION_ID
        )
        mark_migration_complete(
            self.ws, backup_path=None, transition_id=CATALOG_8A0_TRANSITION_ID
        )
        prepare_state_supervision_authority_selection_core_8a2_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertTrue(is_transition_complete(self.ws, CORE1_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, CATALOG_8A0_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertEqual(
            TRANSITION_ID, "state-supervision-authority-selection-core-8a2"
        )

    def test_07_incomplete_blocks_prepare(self) -> None:
        mark_migration_in_progress(
            self.ws,
            backup_path=Path(
                "/tmp/pre_state_supervision_authority_selection_fake.mbbackup"
            ),
            transition_id=TRANSITION_ID,
        )
        with self.assertRaises(MigrationGuardError) as ctx:
            prepare_state_supervision_authority_selection_core_8a2_schema(
                workspace_root=self.ws, database_path=self.db_path
            )
        self.assertIn("nebyla dokončena", str(ctx.exception))
        self.assertNotIn(AUTHORITY_ID_COLUMN, _columns(self.db_path, SUPERVISIONS_TABLE))

    def test_08_ddl_failure_marks_failed(self) -> None:
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_authority_selection_core_8a2_schema_migration."
            "apply_state_supervision_authority_selection_core_8a2_schema_ddl",
            side_effect=RuntimeError("umělá chyba DDL"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_state_supervision_authority_selection_core_8a2_schema(
                    workspace_root=self.ws, database_path=self.db_path
                )
        self.assertTrue(is_migration_failed(self.ws, TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertTrue(
            needs_state_supervision_authority_selection_core_8a2_schema(self.db_path)
        )

    def test_09_allocate_backup_name(self) -> None:
        path = allocate_state_supervision_authority_selection_core_8a2_backup_path(
            self.ws / "zalohy"
        )
        self.assertTrue(path.name.startswith(BACKUP_NAME_PREFIX))
        self.assertTrue(path.name.endswith(".mbbackup"))

    def test_10_upgrade_guard_wires_migration(self) -> None:
        source = inspect.getsource(prepare_database_for_startup)
        self.assertIn(
            "needs_state_supervision_authority_selection_core_8a2_schema", source
        )
        self.assertIn(
            "prepare_state_supervision_authority_selection_core_8a2_schema", source
        )
        self.assertGreaterEqual(
            source.count(
                "prepare_state_supervision_authority_selection_core_8a2_schema("
            ),
            2,
        )


_SVC_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-selection-8a2-svc-"))
with patch.object(Path, "home", return_value=_SVC_HOME):
    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from core.dashboard.attention_service import get_state_supervision_reminder_items
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
        control_authority_catalog_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.control_authority_catalog_tab import (
        ControlAuthorityCatalogTab,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )


class StateSupervisionAuthoritySelectionCore8a2ServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_SVC_HOME)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.db = storage_module.storage_service.database_path
        self.catalog = control_authority_catalog_service
        self.service = state_supervision_service

    def test_01_clean_install_has_new_fields(self) -> None:
        columns = _columns(self.db, SUPERVISIONS_TABLE)
        self.assertIn(AUTHORITY_ID_COLUMN, columns)
        self.assertIn(OFFICE_NAME_SNAPSHOT_COLUMN, columns)
        self.assertIn("authority_office_id", columns)
        self.assertIn(AUTHORITY_ID_INDEX, _indexes(self.db, SUPERVISIONS_TABLE))
        self.assertIn(AUTHORITY_OFFICE_ID_INDEX, _indexes(self.db, SUPERVISIONS_TABLE))

    def test_02_catalog_authority_and_office(self) -> None:
        authority = self.catalog.create_authority(
            code=f"grp-{self.marker}",
            name=f"Skupina {self.marker}",
        )
        office = self.catalog.create_office(
            authority_id=authority.id,
            name=f"Pracoviště {self.marker}",
            address="Adresa pracoviště 1",
        )
        record = self.service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
            authority_office_id=office.id,
            authority_office_name_snapshot=office.name,
            authority_address=office.address,
        )
        loaded = self.service.get_supervision(record.id)
        self.assertEqual(loaded.authority_id, authority.id)
        self.assertEqual(loaded.authority_name, authority.name)
        self.assertEqual(loaded.authority_office_id, office.id)
        self.assertEqual(loaded.authority_office_name_snapshot, office.name)
        self.assertEqual(loaded.authority_address, "Adresa pracoviště 1")

    def test_03_catalog_authority_without_office(self) -> None:
        authority = self.catalog.create_authority(
            code=f"empty-{self.marker}",
            name=f"Skupina bez pracoviště {self.marker}",
        )
        record = self.service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
        )
        loaded = self.service.get_supervision(record.id)
        self.assertEqual(loaded.authority_id, authority.id)
        self.assertEqual(loaded.authority_name, authority.name)
        self.assertIsNone(loaded.authority_office_id)
        self.assertIsNone(loaded.authority_office_name_snapshot)

    def test_04_catalog_authority_manual_office(self) -> None:
        authority = self.catalog.create_authority(
            code=f"mix-{self.marker}",
            name=f"Skupina mix {self.marker}",
        )
        record = self.service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
            authority_office_name_snapshot="Ruční oblastní pracoviště",
            authority_address="Ruční adresa 2",
        )
        loaded = self.service.get_supervision(record.id)
        self.assertEqual(loaded.authority_id, authority.id)
        self.assertIsNone(loaded.authority_office_id)
        self.assertEqual(
            loaded.authority_office_name_snapshot, "Ruční oblastní pracoviště"
        )
        self.assertEqual(loaded.authority_address, "Ruční adresa 2")

    def test_05_manual_authority_and_office(self) -> None:
        record = self.service.create_supervision(
            authority_name=f"Ruční orgán {self.marker}",
            authority_office_name_snapshot="Ruční pracoviště",
            authority_address="Ruční adresa orgánu",
        )
        loaded = self.service.get_supervision(record.id)
        self.assertIsNone(loaded.authority_id)
        self.assertEqual(loaded.authority_name, f"Ruční orgán {self.marker}")
        self.assertIsNone(loaded.authority_office_id)
        self.assertEqual(loaded.authority_office_name_snapshot, "Ruční pracoviště")

    def test_06_omitted_field_keeps_value_none_clears(self) -> None:
        authority = self.catalog.create_authority(
            code=f"keep-{self.marker}",
            name=f"Skupina keep {self.marker}",
        )
        record = self.service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
            authority_office_name_snapshot="Původní pracoviště",
        )
        updated = self.service.update_supervision(record.id, status=record.status)
        self.assertEqual(updated.authority_id, authority.id)
        self.assertEqual(updated.authority_office_name_snapshot, "Původní pracoviště")
        cleared = self.service.update_supervision(
            record.id,
            authority_id=None,
            authority_office_name_snapshot=None,
        )
        self.assertIsNone(cleared.authority_id)
        self.assertIsNone(cleared.authority_office_name_snapshot)
        self.assertEqual(cleared.authority_name, authority.name)

    def test_07_snapshot_not_rewritten_from_catalog(self) -> None:
        authority = self.catalog.create_authority(
            code=f"snap-{self.marker}",
            name="Katalogový název",
        )
        office = self.catalog.create_office(
            authority_id=authority.id,
            name="Katalogové pracoviště",
            address="Katalogová adresa",
        )
        record = self.service.create_supervision(
            authority_name="Historický snapshot orgánu",
            authority_id=authority.id,
            authority_office_id=office.id,
            authority_office_name_snapshot="Historický snapshot pracoviště",
            authority_address="Historická adresa",
        )
        self.catalog.update_authority(authority.id, name="Přejmenovaný orgán")
        self.catalog.update_office(office.id, name="Přejmenované pracoviště")
        loaded = self.service.get_supervision(record.id)
        self.assertEqual(loaded.authority_name, "Historický snapshot orgánu")
        self.assertEqual(
            loaded.authority_office_name_snapshot, "Historický snapshot pracoviště"
        )
        self.assertEqual(loaded.authority_address, "Historická adresa")
        updated = self.service.update_supervision(record.id, file_number="1/2026")
        self.assertEqual(updated.authority_name, "Historický snapshot orgánu")
        self.assertEqual(
            updated.authority_office_name_snapshot, "Historický snapshot pracoviště"
        )
        self.assertEqual(updated.authority_id, authority.id)
        self.assertEqual(updated.authority_office_id, office.id)

    def test_08_inactive_and_missing_catalog_do_not_block(self) -> None:
        authority = self.catalog.create_authority(
            code=f"off-{self.marker}",
            name=f"Neaktivní {self.marker}",
        )
        record = self.service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
        )
        self.catalog.deactivate_authority(authority.id)
        loaded = self.service.get_supervision(record.id)
        self.assertEqual(loaded.authority_id, authority.id)
        updated = self.service.update_supervision(record.id, file_number="2/2026")
        self.assertEqual(updated.authority_id, authority.id)
        ghost = self.service.create_supervision(
            authority_name=f"Bez katalogu {self.marker}",
            authority_id=9_999_001,
            authority_office_id=9_999_002,
        )
        ghost_loaded = self.service.get_supervision(ghost.id)
        self.assertEqual(ghost_loaded.authority_id, 9_999_001)
        self.assertEqual(ghost_loaded.authority_office_id, 9_999_002)

    def test_09_legacy_open_does_not_write_or_backfill(self) -> None:
        record = self.service.create_supervision(
            authority_name=f"OIP {self.marker}",
            authority_ico="87654321",
            authority_address="Adresa 1",
        )
        self.assertIsNone(record.authority_id)
        self.assertIsNone(record.authority_office_name_snapshot)
        before = (
            record.authority_name,
            record.authority_address,
            record.authority_ico,
            record.authority_office_id,
            record.updated_at,
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(hasattr(dialog, "ico_edit"))
        self.assertTrue(hasattr(dialog, "office_combo"))
        self.assertEqual(dialog.office_combo.currentText(), "")
        self.assertNotIn("AUTHORITY_SUGGESTIONS", inspect.getsource(StateSupervisionEditorDialog))
        self.assertNotIn("authority_ico", inspect.getsource(StateSupervisionEditorDialog.get_data))
        self.assertNotIn("ico_edit", inspect.getsource(StateSupervisionEditorDialog.get_snapshot))
        dialog.close()
        reopened = self.service.get_supervision(record.id)
        self.assertEqual(
            (
                reopened.authority_name,
                reopened.authority_address,
                reopened.authority_ico,
                reopened.authority_office_id,
                reopened.updated_at,
            ),
            before,
        )
        self.assertIsNone(reopened.authority_id)
        self.assertIsNone(reopened.authority_office_name_snapshot)

    def test_10_bundle_persists_new_fields(self) -> None:
        authority = self.catalog.create_authority(
            code=f"bun-{self.marker}",
            name=f"Bundle {self.marker}",
        )
        saved, _docs, _timeline = self.service.save_supervision_bundle(
            supervision_id=None,
            fields={
                "authority_name": authority.name,
                "authority_id": authority.id,
                "authority_office_name_snapshot": "Bundle pracoviště",
            },
        )
        loaded = self.service.get_supervision(saved.id)
        self.assertEqual(loaded.authority_id, authority.id)
        self.assertEqual(loaded.authority_office_name_snapshot, "Bundle pracoviště")

    def test_11_isolation_editor_settings_dashboard_agenda(self) -> None:
        editor_source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(editor_source.count("self.tabs.addTab("), 5)
        self.assertNotIn("AUTHORITY_SUGGESTIONS", editor_source)
        self.assertNotIn("ico_edit", editor_source)
        catalog_source = inspect.getsource(ControlAuthorityCatalogTab)
        self.assertNotIn("urllib.request", catalog_source)
        self.assertNotIn("urlopen", catalog_source)
        settings = NastaveniPage()
        titles = [settings.tabs.tabText(i) for i in range(settings.tabs.count())]
        self.assertEqual(
            titles,
            [
                "THP pracovníci",
                "Osoby",
                "Provozy a pracoviště",
                "Státní dozor",
                "Funkce / role",
                "Ohrožené skupiny",
                "Zaměstnavatel",
            ],
        )
        self.assertEqual(settings.tabs.indexOf(settings.workers_tab), 0)
        settings.close()
        items = get_state_supervision_reminder_items()
        self.assertIsInstance(items, list)
        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        page.close()
        dialog = StateSupervisionEditorDialog()
        self.assertEqual(
            [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())],
            [
                TAB_ANNOUNCEMENT,
                TAB_SUBJECT_PREPARATION,
                TAB_COURSE,
                TAB_CONCLUSION,
                TAB_ATTACHMENTS,
            ],
        )
        dialog.close()

    def test_12_incomplete_migration_blocks_startup(self) -> None:
        ws = storage_module.storage_service.base
        db = storage_module.storage_service.database_path
        prepare_database_for_startup(workspace_root=ws, database_path=db)
        state_before = read_migration_state(ws)
        try:
            mark_migration_in_progress(
                ws,
                backup_path=Path(
                    "/tmp/pre_state_supervision_authority_selection_fake.mbbackup"
                ),
                transition_id=TRANSITION_ID,
            )
            with self.assertRaises(MigrationGuardError) as ctx:
                prepare_database_for_startup(
                    workspace_root=ws,
                    database_path=db,
                )
            self.assertIn(TRANSITION_ID, str(ctx.exception))
        finally:
            write_migration_state(ws, state_before)


if __name__ == "__main__":
    unittest.main()
