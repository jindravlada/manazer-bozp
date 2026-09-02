"""STATE-SUPERVISION-AUTHORITY-CATALOG-CORE-8A0: datový základ katalogu."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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


def _seed_pre_8a0_db(db_path: Path) -> None:
    """Existující DB s CORE-1 kontrolou, bez katalogu a bez authority_office_id."""
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
        conn.execute(
            """
            INSERT INTO state_supervisions (
                status, authority_ico, authority_name, authority_address,
                workplace_name_snapshot, workplace_address_snapshot,
                power_of_attorney_required, created_at, updated_at
            ) VALUES (
                'announced', '12345678', 'OIP Praha', 'Kladenská 1',
                'Provoz A', 'Ulice 1',
                0, '2026-03-01 09:00:00', '2026-03-01 09:00:00'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


REQUIRED_AUTHORITY_INDEXES = {
    "uq_control_authorities_code",
    "ix_control_authorities_active",
    "ix_control_authorities_display_order",
    "uq_control_authorities_external_key",
}
REQUIRED_OFFICE_INDEXES = {
    "ix_control_authority_offices_authority_id",
    "ix_control_authority_offices_active",
    "ix_control_authority_offices_display_order",
    "uq_control_authority_offices_external_key",
}

_MIG_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-catalog-8a0-mig-"))
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
    AUTHORITIES_TABLE,
    BACKUP_NAME_PREFIX,
    OFFICES_TABLE,
    TRANSITION_ID,
    allocate_state_supervision_authority_catalog_core_8a0_backup_path,
    needs_state_supervision_authority_catalog_core_8a0_schema,
    prepare_state_supervision_authority_catalog_core_8a0_schema,
)
from moduly.statni_dozor.sluzby.state_supervision_core_1_schema_migration import (  # noqa: E402
    TRANSITION_ID as CORE1_TRANSITION_ID,
)
from moduly.statni_dozor.sluzby.state_supervision_participants_core_3c0_schema_migration import (  # noqa: E402
    TRANSITION_ID as PARTICIPANTS_TRANSITION_ID,
)

_MIG_HOME_PATCHER.stop()


class StateSupervisionAuthorityCatalogCore8a0MigrationTestCase(unittest.TestCase):
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
        _seed_pre_8a0_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_01_backup_before_ddl(self) -> None:
        result = prepare_state_supervision_authority_catalog_core_8a0_schema(
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
        before_tables = _tables(self.db_path)
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_authority_catalog_core_8a0_schema_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_state_supervision_authority_catalog_core_8a0_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertEqual(_tables(self.db_path), before_tables)
        self.assertNotIn(AUTHORITIES_TABLE, before_tables)
        self.assertTrue(
            needs_state_supervision_authority_catalog_core_8a0_schema(self.db_path)
        )

    def test_03_upgrade_adds_tables_and_nullable_office_id(self) -> None:
        prepare_state_supervision_authority_catalog_core_8a0_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertIn(AUTHORITIES_TABLE, _tables(self.db_path))
        self.assertIn(OFFICES_TABLE, _tables(self.db_path))
        self.assertTrue(
            REQUIRED_AUTHORITY_INDEXES.issubset(
                _indexes(self.db_path, AUTHORITIES_TABLE)
            )
        )
        self.assertTrue(
            REQUIRED_OFFICE_INDEXES.issubset(_indexes(self.db_path, OFFICES_TABLE))
        )
        self.assertIn(
            "authority_office_id", _columns(self.db_path, "state_supervisions")
        )
        self.assertIn(
            "ix_state_supervisions_authority_office_id",
            _indexes(self.db_path, "state_supervisions"),
        )
        self.assertNotIn("ico", _columns(self.db_path, AUTHORITIES_TABLE))
        self.assertNotIn("authority_ico", _columns(self.db_path, AUTHORITIES_TABLE))
        self.assertNotIn("ico", _columns(self.db_path, OFFICES_TABLE))
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT authority_name, authority_ico, authority_address, "
                "authority_office_id FROM state_supervisions"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], "OIP Praha")
        self.assertEqual(row[1], "12345678")
        self.assertEqual(row[2], "Kladenská 1")
        self.assertIsNone(row[3])
        self.assertEqual(_count(self.db_path, AUTHORITIES_TABLE), 0)
        self.assertEqual(_count(self.db_path, OFFICES_TABLE), 0)

    def test_04_no_backfill_by_name(self) -> None:
        prepare_state_supervision_authority_catalog_core_8a0_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertEqual(_count(self.db_path, AUTHORITIES_TABLE), 0)
        conn = sqlite3.connect(str(self.db_path))
        try:
            office_id = conn.execute(
                "SELECT authority_office_id FROM state_supervisions"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertIsNone(office_id)

    def test_05_idempotent_repeat(self) -> None:
        first = prepare_state_supervision_authority_catalog_core_8a0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        backups_first = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"))
        self.assertEqual(len(backups_first), 1)
        second = prepare_state_supervision_authority_catalog_core_8a0_schema(
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
            self.ws, backup_path=None, transition_id=PARTICIPANTS_TRANSITION_ID
        )
        prepare_state_supervision_authority_catalog_core_8a0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertTrue(is_transition_complete(self.ws, CORE1_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, PARTICIPANTS_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertEqual(TRANSITION_ID, "state-supervision-authority-catalog-core-8a0")

    def test_07_incomplete_blocks_prepare(self) -> None:
        mark_migration_in_progress(
            self.ws,
            backup_path=Path(
                "/tmp/pre_state_supervision_authority_catalog_fake.mbbackup"
            ),
            transition_id=TRANSITION_ID,
        )
        with self.assertRaises(MigrationGuardError) as ctx:
            prepare_state_supervision_authority_catalog_core_8a0_schema(
                workspace_root=self.ws, database_path=self.db_path
            )
        self.assertIn("nebyla dokončena", str(ctx.exception))
        self.assertNotIn(AUTHORITIES_TABLE, _tables(self.db_path))

    def test_08_ddl_failure_marks_failed(self) -> None:
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_authority_catalog_core_8a0_schema_migration."
            "apply_state_supervision_authority_catalog_core_8a0_schema_ddl",
            side_effect=RuntimeError("umělá chyba DDL"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_state_supervision_authority_catalog_core_8a0_schema(
                    workspace_root=self.ws, database_path=self.db_path
                )
        self.assertTrue(is_migration_failed(self.ws, TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertTrue(
            needs_state_supervision_authority_catalog_core_8a0_schema(self.db_path)
        )

    def test_09_allocate_backup_name(self) -> None:
        path = allocate_state_supervision_authority_catalog_core_8a0_backup_path(
            self.ws / "zalohy"
        )
        self.assertTrue(path.name.startswith(BACKUP_NAME_PREFIX))
        self.assertTrue(path.name.endswith(".mbbackup"))

    def test_10_upgrade_guard_wires_migration(self) -> None:
        source = inspect.getsource(prepare_database_for_startup)
        self.assertIn(
            "needs_state_supervision_authority_catalog_core_8a0_schema", source
        )
        self.assertIn(
            "prepare_state_supervision_authority_catalog_core_8a0_schema", source
        )
        self.assertGreaterEqual(
            source.count(
                "prepare_state_supervision_authority_catalog_core_8a0_schema("
            ),
            2,
        )


_SVC_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-catalog-8a0-svc-"))
with patch.object(Path, "home", return_value=_SVC_HOME):
    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from core.dashboard.attention_service import get_state_supervision_reminder_items
    from core.database.upgrade_guard import (  # noqa: E402
        MigrationGuardError,
        is_migration_failed,
        is_transition_complete,
        mark_migration_complete,
        mark_migration_in_progress,
        prepare_database_for_startup,
        read_migration_state,
        write_migration_state,
    )
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        AUTHORITY_HAS_ACTIVE_OFFICES_MESSAGE,
        AUTHORITY_ORIGIN_BUNDLED,
        AUTHORITY_ORIGIN_MANUAL,
        AUTHORITY_ORIGIN_WEB,
        AUTHORITY_SUGGESTIONS,
        OFFICE_ACTIVE_UNDER_INACTIVE_AUTHORITY_MESSAGE,
        OFFICE_KIND_REGIONAL,
        OFFICE_KIND_TERRITORIAL,
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
        ControlAuthorityCatalogError,
        ControlAuthorityCatalogService,
        control_authority_catalog_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )


class StateSupervisionAuthorityCatalogCore8a0ServiceTestCase(unittest.TestCase):
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
        self.service = control_authority_catalog_service

    def test_01_clean_install_creates_empty_catalog(self) -> None:
        db = storage_module.storage_service.database_path
        self.assertIn(AUTHORITIES_TABLE, _tables(db))
        self.assertIn(OFFICES_TABLE, _tables(db))
        self.assertIn("authority_office_id", _columns(db, "state_supervisions"))
        self.assertTrue(
            REQUIRED_AUTHORITY_INDEXES.issubset(_indexes(db, AUTHORITIES_TABLE))
        )
        self.assertTrue(REQUIRED_OFFICE_INDEXES.issubset(_indexes(db, OFFICES_TABLE)))
        # Seed 8A1 plní výchozí katalog; 8A0 ověřuje jen existenci schématu.

    def test_02_create_authority_minimal_and_unique_code(self) -> None:
        authority = self.service.create_authority(
            code=f"  KHS {self.marker} ",
            name="Krajská hygienická stanice",
        )
        self.assertEqual(authority.code, f"khs-{self.marker}")
        self.assertEqual(authority.name, "Krajská hygienická stanice")
        self.assertEqual(authority.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertIsNotNone(authority.user_edited_at)
        self.assertIsNone(authority.last_checked_at)
        self.assertIsNone(authority.abbreviation)
        self.assertIsNone(authority.external_key)
        with self.assertRaises(ControlAuthorityCatalogError):
            self.service.create_authority(
                code=f"KHS {self.marker}",
                name="Duplicitní",
            )
        loaded = self.service.get_authority_by_code(f"khs-{self.marker}")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, authority.id)

    def test_03_origin_and_external_key(self) -> None:
        with self.assertRaises(ControlAuthorityCatalogError):
            self.service.create_imported_authority(
                code=f"bad-{self.marker}",
                name="Špatný původ",
                origin="unknown",
            )
        bundled = self.service.create_imported_authority(
            code=f"suip-{self.marker}",
            name="SÚIP",
            origin=AUTHORITY_ORIGIN_BUNDLED,
            external_key=f"suip:{self.marker}",
            last_checked_at=datetime(2026, 9, 2, 10, 0, 0),
        )
        self.assertEqual(bundled.origin, AUTHORITY_ORIGIN_BUNDLED)
        self.assertIsNone(bundled.user_edited_at)
        self.assertEqual(bundled.last_checked_at, datetime(2026, 9, 2, 10, 0, 0))
        with self.assertRaises(ControlAuthorityCatalogError):
            self.service.create_authority(
                code=f"other-{self.marker}",
                name="Jiný",
                external_key=f"suip:{self.marker}",
            )
        self.service.create_authority(
            code=f"empty-key-{self.marker}",
            name="Bez klíče",
            external_key="   ",
        )
        second_null = self.service.create_authority(
            code=f"also-empty-{self.marker}",
            name="Také bez klíče",
        )
        self.assertIsNone(second_null.external_key)

    def test_04_update_authority_sets_manual_and_keeps_check_date(self) -> None:
        checked = datetime(2026, 1, 15, 8, 0, 0)
        authority = self.service.create_imported_authority(
            code=f"cbu-{self.marker}",
            name="ČBÚ",
            origin=AUTHORITY_ORIGIN_WEB,
            last_checked_at=checked,
        )
        updated = self.service.update_authority(
            authority.id,
            name="Český báňský úřad",
            abbreviation="ČBÚ",
            website="https://cbu.gov.cz/cs/",
        )
        self.assertEqual(updated.name, "Český báňský úřad")
        self.assertEqual(updated.abbreviation, "ČBÚ")
        self.assertEqual(updated.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertIsNotNone(updated.user_edited_at)
        self.assertEqual(updated.last_checked_at, checked)

    def test_05_deactivate_authority_rejects_active_offices(self) -> None:
        authority = self.service.create_authority(
            code=f"hzs-{self.marker}",
            name="HZS ČR",
        )
        office = self.service.create_office(
            authority_id=authority.id,
            name="HZS Ústeckého kraje",
        )
        with self.assertRaises(ControlAuthorityCatalogError) as ctx:
            self.service.deactivate_authority(authority.id)
        self.assertEqual(str(ctx.exception), AUTHORITY_HAS_ACTIVE_OFFICES_MESSAGE)
        self.service.deactivate_office(office.id)
        deactivated = self.service.deactivate_authority(authority.id)
        self.assertFalse(deactivated.active)
        still = self.service.get_office(office.id)
        self.assertIsNotNone(still)
        self.assertFalse(still.active)
        reactivated = self.service.reactivate_authority(authority.id)
        self.assertTrue(reactivated.active)
        office_after = self.service.get_office(office.id)
        self.assertFalse(office_after.active)

    def test_06_search_and_sort_authorities(self) -> None:
        self.service.create_authority(
            code=f"zeta-{self.marker}",
            name="Zeta úřad",
            display_order=2,
            abbreviation="ZU",
        )
        self.service.create_authority(
            code=f"alfa-{self.marker}",
            name="Alfa úřad",
            display_order=2,
        )
        self.service.create_authority(
            code=f"first-{self.marker}",
            name="První",
            display_order=0,
        )
        listed = [
            item
            for item in self.service.list_authorities()
            if self.marker in item.code
        ]
        names = [item.name for item in listed]
        self.assertEqual(names[0], "První")
        self.assertEqual(names[1:], ["Alfa úřad", "Zeta úřad"])
        found = self.service.list_authorities(query=f"zeta-{self.marker}")
        self.assertEqual(len(found), 1)
        found_abbr = self.service.list_authorities(query="ZU")
        self.assertTrue(any(item.code == f"zeta-{self.marker}" for item in found_abbr))

    def test_07_no_public_delete(self) -> None:
        service_source = inspect.getsource(ControlAuthorityCatalogService)
        repo_source = inspect.getsource(
            type(self.service.repository)
        )
        self.assertNotIn("def delete(", service_source)
        self.assertNotIn("def delete_", service_source)
        self.assertNotIn("def delete(", repo_source)
        self.assertNotIn("session.delete(", service_source)

    def test_08_create_office_without_ico(self) -> None:
        authority = self.service.create_authority(
            code=f"du-{self.marker}",
            name="Drážní úřad",
        )
        office = self.service.create_office(
            authority_id=authority.id,
            name="Pracoviště Plzeň",
            address="Škroupova 11, Plzeň",
            phone="+420 972 524 098",
            email=" podatelna@du.gov.cz ",
            website="https://du.gov.cz/kontakty/",
            territorial_scope="Plzeňský kraj",
            office_kind=OFFICE_KIND_REGIONAL,
        )
        self.assertEqual(office.email, "podatelna@du.gov.cz")
        self.assertEqual(office.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertIsNone(getattr(office, "ico", None))
        db = storage_module.storage_service.database_path
        self.assertNotIn("ico", _columns(db, OFFICES_TABLE))
        with self.assertRaises(ControlAuthorityCatalogError):
            self.service.create_office(
                authority_id=authority.id,
                name=" ",
            )
        with self.assertRaises(ControlAuthorityCatalogError):
            self.service.create_office(
                authority_id=authority.id,
                name="Neznámý druh",
                office_kind="branch",
            )

    def test_09_active_office_only_under_active_parent(self) -> None:
        authority = self.service.create_authority(
            code=f"parent-{self.marker}",
            name="Rodič",
        )
        inactive_office = self.service.create_office(
            authority_id=authority.id,
            name="K deaktivaci",
            active=True,
        )
        self.service.deactivate_office(inactive_office.id)
        self.service.deactivate_authority(authority.id)
        with self.assertRaises(ControlAuthorityCatalogError) as ctx:
            self.service.create_office(
                authority_id=authority.id,
                name="Aktivní pod neaktivním",
            )
        self.assertEqual(
            str(ctx.exception), OFFICE_ACTIVE_UNDER_INACTIVE_AUTHORITY_MESSAGE
        )
        allowed = self.service.create_office(
            authority_id=authority.id,
            name="Neaktivní pod neaktivním",
            active=False,
        )
        self.assertFalse(allowed.active)
        with self.assertRaises(ControlAuthorityCatalogError):
            self.service.reactivate_office(inactive_office.id)

    def test_10_update_office_contacts_and_kinds(self) -> None:
        authority = self.service.create_authority(
            code=f"khs-{self.marker}",
            name="KHS",
        )
        office = self.service.create_office(
            authority_id=authority.id,
            name="Územní pracoviště Teplice",
            office_kind=OFFICE_KIND_TERRITORIAL,
        )
        updated = self.service.update_office(
            office.id,
            address="Teplice 1",
            phone="123",
            email="teplice@example.cz",
            territorial_scope="okres Teplice",
        )
        self.assertEqual(updated.address, "Teplice 1")
        self.assertEqual(updated.phone, "123")
        self.assertEqual(updated.email, "teplice@example.cz")
        self.assertEqual(updated.origin, AUTHORITY_ORIGIN_MANUAL)

    def test_11_office_filter_search_and_unique_key(self) -> None:
        first = self.service.create_authority(
            code=f"a-{self.marker}",
            name="První orgán",
        )
        second = self.service.create_authority(
            code=f"b-{self.marker}",
            name="Druhý orgán",
        )
        self.service.create_office(
            authority_id=first.id,
            name="Teplice",
            address="Teplická 1",
            territorial_scope="Ústecký kraj",
            external_key=f"khs:teplice:{self.marker}",
            display_order=5,
        )
        self.service.create_office(
            authority_id=first.id,
            name="Most",
            display_order=1,
        )
        other = self.service.create_office(
            authority_id=second.id,
            name="Jiné",
        )
        self.service.deactivate_office(other.id)
        only_first = self.service.list_offices(authority_id=first.id)
        self.assertEqual([item.name for item in only_first], ["Most", "Teplice"])
        self.assertEqual(
            len(self.service.list_offices(authority_id=second.id)), 0
        )
        self.assertEqual(
            len(
                self.service.list_offices(
                    authority_id=second.id, include_inactive=True
                )
            ),
            1,
        )
        found = self.service.list_offices(query="Teplická")
        self.assertEqual(len(found), 1)
        found_scope = self.service.list_offices(query="Ústecký")
        self.assertEqual(found_scope[0].name, "Teplice")
        with self.assertRaises(ControlAuthorityCatalogError):
            self.service.create_office(
                authority_id=second.id,
                name="Duplicitní klíč",
                external_key=f"khs:teplice:{self.marker}",
            )

    def test_12_no_cascade_delete(self) -> None:
        authority = self.service.create_authority(
            code=f"fk-{self.marker}",
            name="FK orgán",
        )
        office = self.service.create_office(
            authority_id=authority.id,
            name="Pobočka",
            active=False,
        )
        self.service.deactivate_authority(authority.id)
        self.assertIsNotNone(self.service.get_office(office.id))
        db = storage_module.storage_service.database_path
        conn = sqlite3.connect(str(db))
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "DELETE FROM control_authorities WHERE id = ?",
                    (authority.id,),
                )
                conn.commit()
        finally:
            conn.close()

    def test_13_supervision_unchanged_and_null_office_id(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"OIP {self.marker}",
            authority_ico="87654321",
            authority_address="Adresa 1",
        )
        self.assertIsNone(getattr(record, "authority_office_id", None) or None)
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.authority_ico, "87654321")
        self.assertEqual(loaded.authority_name, f"OIP {self.marker}")
        self.assertIsNone(loaded.authority_office_id)

    def test_14_isolation_editor_settings_dashboard_agenda(self) -> None:
        service_source = inspect.getsource(ControlAuthorityCatalogService)
        self.assertNotIn("PySide", service_source)
        self.assertNotIn("Qt", service_source)
        editor_source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(editor_source.count("self.tabs.addTab("), 5)
        self.assertIn("AUTHORITY_SUGGESTIONS", editor_source)
        self.assertIn("ico_edit", editor_source)
        self.assertIn("LABEL_AUTHORITY_ICO", editor_source)

        record = state_supervision_service.create_supervision(
            authority_name=f"OIP {self.marker}",
            authority_ico="11112222",
        )
        db = storage_module.storage_service.database_path
        before_auth = _count(db, AUTHORITIES_TABLE)
        before_off = _count(db, OFFICES_TABLE)
        loaded = state_supervision_service.get_supervision(record.id)
        before_updated = loaded.updated_at
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(dialog.tabs.count(), 5)
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
        self.assertTrue(hasattr(dialog, "authority_combo"))
        self.assertTrue(hasattr(dialog, "ico_edit"))
        self.assertFalse(hasattr(dialog, "office_combo"))
        self.assertEqual(list(AUTHORITY_SUGGESTIONS)[0], "Obvodní báňský úřad (OBÚ)")
        dialog.close()
        reopened = state_supervision_service.get_supervision(record.id)
        self.assertEqual(reopened.authority_ico, "11112222")
        self.assertEqual(reopened.updated_at, before_updated)
        self.assertEqual(_count(db, AUTHORITIES_TABLE), before_auth)
        self.assertEqual(_count(db, OFFICES_TABLE), before_off)

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

    def test_15_incomplete_migration_blocks_startup(self) -> None:
        ws = storage_module.storage_service.base
        db = storage_module.storage_service.database_path
        prepare_database_for_startup(workspace_root=ws, database_path=db)
        state_before = read_migration_state(ws)
        try:
            mark_migration_in_progress(
                ws,
                backup_path=Path(
                    "/tmp/pre_state_supervision_authority_catalog_fake.mbbackup"
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
