"""STATE-SUPERVISION-CORE-1: migrace, model a služba — bez UI."""

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


def _seed_pre_core1_db(db_path: Path) -> None:
    """Existující DB bez tabulky státního dozoru."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            side.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE audits (
                id INTEGER PRIMARY KEY,
                number VARCHAR(30) DEFAULT '',
                year INTEGER,
                status VARCHAR(30) DEFAULT 'Plánováno' NOT NULL,
                title VARCHAR(250) DEFAULT '',
                workplace_name VARCHAR(150) DEFAULT '',
                created_at DATETIME,
                updated_at DATETIME
            );
            INSERT INTO audits (id, number, year, status, title, workplace_name)
            VALUES (1, 'A-1', 2026, 'Probíhá', 'Interní legacy', 'Provoz X');
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                title VARCHAR(250) DEFAULT '',
                status VARCHAR(40) DEFAULT 'Aktivní'
            );
            INSERT INTO tasks (id, title) VALUES (1, 'Úkol legacy');
            CREATE TABLE external_audits (
                id INTEGER PRIMARY KEY,
                organization_name VARCHAR(250) NOT NULL DEFAULT '',
                status VARCHAR(40) NOT NULL DEFAULT 'planned'
            );
            INSERT INTO external_audits (id, organization_name)
            VALUES (1, 'Certifikační orgán');
            """
        )
        conn.commit()
    finally:
        conn.close()


REQUIRED_INDEXES = {
    "ix_state_supervisions_status",
    "ix_state_supervisions_authority_name",
    "ix_state_supervisions_workplace_id",
    "ix_state_supervisions_started_at",
    "ix_state_supervisions_ended_at",
    "ix_state_supervisions_closed_at",
}

_MIG_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-core-1-mig-"))
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
    is_migration_in_progress,
    is_transition_complete,
    mark_migration_in_progress,
    prepare_database_for_startup,
    read_migration_state,
    write_migration_state,
)
from moduly.statni_dozor.sluzby.state_supervision_core_1_schema_migration import (  # noqa: E402
    BACKUP_NAME_PREFIX,
    TABLE_NAME,
    TRANSITION_ID,
    allocate_state_supervision_core_1_backup_path,
    needs_state_supervision_core_1_schema,
    prepare_state_supervision_core_1_schema,
    schema_is_present,
)

_MIG_HOME_PATCHER.stop()


class StateSupervisionCore1MigrationTestCase(unittest.TestCase):
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
        for backup in (self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"):
            backup.unlink()
        _seed_pre_core1_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_01_backup_before_ddl(self) -> None:
        result = prepare_state_supervision_core_1_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertTrue(result.migrated)
        assert result.pre_migration_backup_path is not None
        self.assertTrue(result.pre_migration_backup_path.is_file())
        self.assertTrue(
            result.pre_migration_backup_path.name.startswith(f"{BACKUP_NAME_PREFIX}_")
        )
        self.assertEqual(result.pre_migration_backup_path.suffix, ".mbbackup")

    def test_02_backup_failure_no_table(self) -> None:
        before = _tables(self.db_path)
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_core_1_schema_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_state_supervision_core_1_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertTrue(needs_state_supervision_core_1_schema(self.db_path))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.ws, TRANSITION_ID))
        self.assertEqual(_tables(self.db_path), before)
        self.assertNotIn(TABLE_NAME, before)

    def test_03_successful_additive_migration(self) -> None:
        before = _tables(self.db_path)
        audits_before = _count(self.db_path, "audits")
        tasks_before = _count(self.db_path, "tasks")
        ea_before = _count(self.db_path, "external_audits")
        conn = sqlite3.connect(str(self.db_path))
        try:
            internal_row = conn.execute(
                "SELECT title, status FROM audits WHERE id = 1"
            ).fetchone()
            ea_row = conn.execute(
                "SELECT organization_name FROM external_audits WHERE id = 1"
            ).fetchone()
        finally:
            conn.close()

        result = prepare_state_supervision_core_1_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertTrue(result.migrated)
        self.assertTrue(schema_is_present(self.db_path))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertEqual(_tables(self.db_path) - before, {TABLE_NAME})
        self.assertEqual(_count(self.db_path, TABLE_NAME), 0)
        self.assertEqual(_count(self.db_path, "audits"), audits_before)
        self.assertEqual(_count(self.db_path, "tasks"), tasks_before)
        self.assertEqual(_count(self.db_path, "external_audits"), ea_before)
        conn = sqlite3.connect(str(self.db_path))
        try:
            internal_after = conn.execute(
                "SELECT title, status FROM audits WHERE id = 1"
            ).fetchone()
            ea_after = conn.execute(
                "SELECT organization_name FROM external_audits WHERE id = 1"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(internal_after, internal_row)
        self.assertEqual(ea_after, ea_row)
        self.assertTrue(REQUIRED_INDEXES.issubset(_indexes(self.db_path, TABLE_NAME)))

    def test_04_idempotent_repeat(self) -> None:
        first = prepare_state_supervision_core_1_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        backups_first = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertEqual(len(backups_first), 1)
        second = prepare_state_supervision_core_1_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertFalse(second.migrated)
        backups_second = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertEqual(len(backups_second), 1)
        self.assertEqual(first.pre_migration_backup_path, backups_second[0])

    def test_05_completed_marker_missing_schema_repairs(self) -> None:
        prepare_state_supervision_core_1_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(f'DROP TABLE "{TABLE_NAME}"')
            conn.commit()
        finally:
            conn.close()
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertTrue(needs_state_supervision_core_1_schema(self.db_path))

        result = prepare_state_supervision_core_1_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertTrue(result.migrated)
        self.assertIsNotNone(result.pre_migration_backup_path)
        self.assertTrue(schema_is_present(self.db_path))
        backups = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertGreaterEqual(len(backups), 2)

    def test_06_ddl_failure_marks_failed(self) -> None:
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_core_1_schema_migration."
            "apply_state_supervision_core_1_schema_ddl",
            side_effect=RuntimeError("umělá chyba DDL"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_state_supervision_core_1_schema(
                    workspace_root=self.ws, database_path=self.db_path
                )
        self.assertTrue(is_migration_failed(self.ws, TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertTrue(needs_state_supervision_core_1_schema(self.db_path))

    def test_07_incomplete_blocks_prepare(self) -> None:
        mark_migration_in_progress(
            self.ws,
            backup_path=Path("/tmp/pre_state_supervision_core_fake.mbbackup"),
            transition_id=TRANSITION_ID,
        )
        with self.assertRaises(MigrationGuardError) as ctx:
            prepare_state_supervision_core_1_schema(
                workspace_root=self.ws, database_path=self.db_path
            )
        self.assertIn("nebyla dokončena", str(ctx.exception))
        self.assertNotIn(TABLE_NAME, _tables(self.db_path))

    def test_08_allocate_backup_name(self) -> None:
        path = allocate_state_supervision_core_1_backup_path(self.ws / "zalohy")
        self.assertTrue(path.name.startswith(f"{BACKUP_NAME_PREFIX}_"))
        self.assertTrue(path.name.endswith(".mbbackup"))

    def test_09_upgrade_guard_wires_migration(self) -> None:
        source = inspect.getsource(prepare_database_for_startup)
        self.assertIn("needs_state_supervision_core_1_schema", source)
        self.assertIn("prepare_state_supervision_core_1_schema", source)
        self.assertGreaterEqual(source.count("prepare_state_supervision_core_1_schema("), 2)

    def test_10_first_agenda_and_calendar_isolated(self) -> None:
        root = Path(__file__).resolve().parents[1]
        service = (root / "moduly" / "agenda" / "sluzby" / "agenda_service.py").read_text(
            encoding="utf-8"
        )
        calendar = (
            root / "core" / "dashboard" / "widget_calendar_placeholder.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("statni_dozor", service)
        self.assertNotIn("state_supervision", service)
        self.assertNotIn("statni_dozor", calendar)
        self.assertNotIn("state_supervision", calendar)


_SVC_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-core-1-svc-"))
with patch.object(Path, "home", return_value=_SVC_HOME):
    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.statni_dozor.constants import (
        DEFAULT_STATUS,
        MODULE_KEY,
        MODULE_NAME,
        STATE_SUPERVISION_NOTIFICATION_METHODS,
        STATE_SUPERVISION_STATUS_LABELS,
        STATE_SUPERVISION_STATUSES,
        STATUS_ANNOUNCED,
        STATUS_CANCELLED,
        STATUS_CLOSED,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )


class StateSupervisionCore1ServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
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
        suffix = uuid.uuid4().hex[:6]
        self.workplace = settings_service.save_workplace(
            name=f"SD-WP-{suffix}",
            address=f"Ulice {suffix}",
            active=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )

    def _create(self, **fields):
        payload = {"authority_name": "OIP Praha"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def test_01_clean_install_creates_table(self) -> None:
        db = storage_module.storage_service.database_path
        self.assertIn(TABLE_NAME, _tables(db))
        self.assertTrue(REQUIRED_INDEXES.issubset(_indexes(db, TABLE_NAME)))
        self.assertEqual(MODULE_KEY, "state_supervision")
        self.assertEqual(MODULE_NAME, "Státní dozor")

    def test_02_minimal_create_defaults_to_announced(self) -> None:
        record = self._create()
        self.assertIsNotNone(record.id)
        self.assertEqual(record.status, STATUS_ANNOUNCED)
        self.assertEqual(record.status, DEFAULT_STATUS)
        self.assertEqual(record.authority_name, "OIP Praha")
        self.assertIsNone(record.authority_ico)
        self.assertIsNone(record.subject)
        self.assertIsNone(record.file_number)
        self.assertIsNone(record.result)
        self.assertFalse(record.power_of_attorney_required)
        loaded = state_supervision_service.get_supervision(record.id)
        assert loaded is not None
        self.assertEqual(loaded.authority_name, "OIP Praha")
        self.assertEqual(loaded.status, STATUS_ANNOUNCED)

    def test_03_update_fields(self) -> None:
        record = self._create()
        updated = state_supervision_service.update_supervision(
            record.id,
            file_number="ČJ/2026/1",
            subject="Kontrola BOZP",
            result="Bez závad",
        )
        self.assertEqual(updated.file_number, "ČJ/2026/1")
        self.assertEqual(updated.subject, "Kontrola BOZP")
        self.assertEqual(updated.result, "Bez závad")
        self.assertEqual(updated.status, STATUS_ANNOUNCED)

    def test_04_all_canonical_statuses(self) -> None:
        self.assertEqual(set(STATE_SUPERVISION_STATUS_LABELS), STATE_SUPERVISION_STATUSES)
        record = self._create()
        for status in STATE_SUPERVISION_STATUSES:
            updated = state_supervision_service.update_supervision(
                record.id, status=status
            )
            self.assertEqual(updated.status, status)

    def test_05_reject_unknown_status(self) -> None:
        with self.assertRaises(StateSupervisionError):
            self._create(status="draft")
        record = self._create()
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.update_supervision(record.id, status="hotovo")

    def test_06_all_notification_methods(self) -> None:
        for method in STATE_SUPERVISION_NOTIFICATION_METHODS:
            record = self._create(notification_method=method)
            self.assertEqual(record.notification_method, method)

    def test_07_reject_unknown_notification_method(self) -> None:
        with self.assertRaises(StateSupervisionError):
            self._create(notification_method="fax")

    def test_08_date_order_validation(self) -> None:
        started = datetime(2026, 3, 10, 9, 0, 0)
        ended = datetime(2026, 3, 9, 17, 0, 0)
        with self.assertRaises(StateSupervisionError):
            self._create(started_at=started, ended_at=ended)
        record = self._create(started_at=started, ended_at=datetime(2026, 3, 11, 12, 0))
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.update_supervision(
                record.id, ended_at=datetime(2026, 3, 8, 8, 0)
            )
        protocol = datetime(2026, 4, 1, 10, 0)
        objections = datetime(2026, 3, 31, 10, 0)
        with self.assertRaises(StateSupervisionError):
            self._create(
                protocol_received_at=protocol,
                objections_submitted_at=objections,
            )
        ok = self._create(
            protocol_received_at=protocol,
            objections_submitted_at=datetime(2026, 4, 2, 8, 0),
        )
        self.assertEqual(ok.protocol_received_at, protocol)

    def test_09_empty_optional_and_czech_multiline(self) -> None:
        text = "Předmět kontroly:\npracoviště v České republice"
        record = self._create(
            subject=text,
            initial_information=text,
            preparation_note="",
            notification_note=None,
            file_number="  ",
        )
        self.assertEqual(record.subject, text)
        self.assertEqual(record.initial_information, text)
        self.assertIsNone(record.preparation_note)
        self.assertIsNone(record.file_number)
        self.assertIsNone(record.notification_method)

    def test_10_closed_and_cancelled_remain_in_list(self) -> None:
        marker = uuid.uuid4().hex[:8]
        active = self._create(authority_name=f"OIP {marker}")
        closed = self._create(
            authority_name=f"OIP {marker}",
            status=STATUS_CLOSED,
        )
        cancelled = self._create(
            authority_name=f"OIP {marker}",
            status=STATUS_CANCELLED,
        )
        listed = state_supervision_service.list_supervisions(query=marker)
        ids = {item.id for item in listed}
        self.assertIn(active.id, ids)
        self.assertIn(closed.id, ids)
        self.assertIn(cancelled.id, ids)

    def test_11_default_sort_and_filters(self) -> None:
        marker = uuid.uuid4().hex[:8]
        old_started = self._create(
            authority_name=f"OIP {marker}",
            started_at=datetime(2024, 1, 15, 8, 0),
        )
        planned_only = self._create(
            authority_name=f"SÚIP {marker}",
            planned_start_at=datetime(2025, 6, 1, 9, 0),
            workplace_id=self.workplace.id,
        )
        created_only = self._create(authority_name=f"OIP {marker}")
        ordered = [
            item.id
            for item in state_supervision_service.list_supervisions(query=marker)
        ]
        self.assertEqual(ordered, [created_only.id, planned_only.id, old_started.id])

        by_status = state_supervision_service.list_supervisions(
            status=STATUS_ANNOUNCED, query=marker
        )
        self.assertEqual({item.id for item in by_status}, set(ordered))

        by_year = state_supervision_service.list_supervisions(year=2025, query=marker)
        self.assertEqual([item.id for item in by_year], [planned_only.id])

        by_authority = state_supervision_service.list_supervisions(
            authority="SÚIP", query=marker
        )
        self.assertEqual([item.id for item in by_authority], [planned_only.id])

        by_workplace = state_supervision_service.list_supervisions(
            workplace_id=self.workplace.id, query=marker
        )
        self.assertEqual([item.id for item in by_workplace], [planned_only.id])

    def test_12_no_public_delete(self) -> None:
        public = [
            name
            for name in dir(StateSupervisionService)
            if not name.startswith("_")
        ]
        self.assertNotIn("delete", public)
        self.assertNotIn("delete_supervision", public)
        self.assertNotIn("remove", public)
        self.assertNotIn("remove_supervision", public)
        source = inspect.getsource(StateSupervisionService)
        self.assertNotIn("session.delete", source)

    def test_13_workplace_rename_keeps_snapshot(self) -> None:
        original_name = self.workplace.name
        original_address = self.workplace.address
        record = self._create(workplace_id=self.workplace.id)
        self.assertEqual(record.workplace_name_snapshot, original_name)
        self.assertEqual(record.workplace_address_snapshot, original_address)

        settings_service.save_workplace(
            id=self.workplace.id,
            name=f"Přejmenováno-{uuid.uuid4().hex[:4]}",
            address="Nová adresa 1",
            active=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        loaded = state_supervision_service.get_supervision(record.id)
        assert loaded is not None
        self.assertEqual(loaded.workplace_name_snapshot, original_name)
        self.assertEqual(loaded.workplace_address_snapshot, original_address)
        self.assertEqual(loaded.workplace_id, self.workplace.id)

    def test_14_reject_empty_authority_name(self) -> None:
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.create_supervision(authority_name="  ")

    def test_15_incomplete_migration_blocks_startup(self) -> None:
        ws = storage_module.storage_service.base
        db = storage_module.storage_service.database_path
        prepare_database_for_startup(workspace_root=ws, database_path=db)
        state_before = read_migration_state(ws)
        try:
            mark_migration_in_progress(
                ws,
                backup_path=Path("/tmp/pre_state_supervision_core_fake.mbbackup"),
                transition_id=TRANSITION_ID,
            )
            with self.assertRaises(MigrationGuardError) as ctx:
                prepare_database_for_startup(
                    workspace_root=ws,
                    database_path=db,
                )
            self.assertIn("STATE-SUPERVISION-CORE-1", str(ctx.exception))
        finally:
            write_migration_state(ws, state_before)


if __name__ == "__main__":
    unittest.main()
