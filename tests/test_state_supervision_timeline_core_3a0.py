"""STATE-SUPERVISION-TIMELINE-CORE-3A0: datový základ průběhu kontroly."""

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


def _index_columns(db_path: Path, table: str) -> dict[str, list[str]]:
    conn = sqlite3.connect(str(db_path))
    try:
        result: dict[str, list[str]] = {}
        for row in conn.execute(f'PRAGMA index_list("{table}")').fetchall():
            name = str(row[1])
            cols = [
                str(info[2])
                for info in conn.execute(f'PRAGMA index_info("{name}")').fetchall()
            ]
            result[name] = cols
        return result
    finally:
        conn.close()


def _seed_pre_3a0_db(db_path: Path) -> None:
    """Existující DB s kontrolami CORE-1 a doklady 2C0, bez tabulky průběhu."""
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
                title VARCHAR(250) DEFAULT ''
            );
            INSERT INTO audits (id, title) VALUES (1, 'Interní legacy');
            CREATE TABLE state_supervisions (
                id INTEGER PRIMARY KEY,
                status VARCHAR(40) NOT NULL DEFAULT 'announced',
                authority_name VARCHAR(250) NOT NULL,
                workplace_name_snapshot VARCHAR(150) NOT NULL DEFAULT '',
                workplace_address_snapshot VARCHAR(250) NOT NULL DEFAULT '',
                power_of_attorney_required BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME
            );
            INSERT INTO state_supervisions (id, status, authority_name)
            VALUES (1, 'announced', 'OIP Legacy'),
                   (2, 'closed', 'KHS Legacy');
            CREATE TABLE state_supervision_required_documents (
                id INTEGER PRIMARY KEY,
                state_supervision_id INTEGER NOT NULL,
                title VARCHAR(250) NOT NULL,
                responsible_source_type VARCHAR(40),
                responsible_source_id INTEGER,
                responsible_name_snapshot VARCHAR(250),
                due_at DATETIME,
                prepared_at DATETIME,
                submitted_at DATETIME,
                note TEXT,
                display_order INTEGER NOT NULL DEFAULT 0,
                active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(state_supervision_id) REFERENCES state_supervisions (id)
            );
            INSERT INTO state_supervision_required_documents (
                id, state_supervision_id, title, display_order, active
            ) VALUES (1, 1, 'Bezpečnostní listy', 0, 1);
            """
        )
        conn.commit()
    finally:
        conn.close()


REQUIRED_INDEXES = {
    "ix_state_supervision_timeline_items_state_supervision_id",
    "ix_state_supervision_timeline_items_list",
    "ix_state_supervision_timeline_items_occurred_at",
}

_MIG_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-timeline-3a0-mig-"))
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
    mark_migration_complete,
    mark_migration_in_progress,
    prepare_database_for_startup,
    read_migration_state,
    write_migration_state,
)
from moduly.statni_dozor.sluzby.state_supervision_core_1_schema_migration import (  # noqa: E402
    TRANSITION_ID as CORE1_TRANSITION_ID,
)
from moduly.statni_dozor.sluzby.state_supervision_documents_core_2c0_schema_migration import (  # noqa: E402
    TRANSITION_ID as DOCUMENTS_TRANSITION_ID,
)
from moduly.statni_dozor.sluzby.state_supervision_timeline_core_3a0_schema_migration import (  # noqa: E402
    BACKUP_NAME_PREFIX,
    TABLE_NAME,
    TRANSITION_ID,
    allocate_state_supervision_timeline_core_3a0_backup_path,
    needs_state_supervision_timeline_core_3a0_schema,
    prepare_state_supervision_timeline_core_3a0_schema,
    schema_is_present,
)

_MIG_HOME_PATCHER.stop()


class StateSupervisionTimelineCore3a0MigrationTestCase(unittest.TestCase):
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
        _seed_pre_3a0_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_01_backup_before_ddl(self) -> None:
        result = prepare_state_supervision_timeline_core_3a0_schema(
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
        self.assertIn("pre_state_supervision_timeline_", result.pre_migration_backup_path.name)

    def test_02_backup_failure_no_table(self) -> None:
        before = _tables(self.db_path)
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_timeline_core_3a0_schema_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_state_supervision_timeline_core_3a0_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertTrue(needs_state_supervision_timeline_core_3a0_schema(self.db_path))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.ws, TRANSITION_ID))
        self.assertEqual(_tables(self.db_path), before)
        self.assertNotIn(TABLE_NAME, before)

    def test_03_successful_additive_no_backfill(self) -> None:
        before = _tables(self.db_path)
        supervisions_before = _count(self.db_path, "state_supervisions")
        documents_before = _count(
            self.db_path, "state_supervision_required_documents"
        )
        audits_before = _count(self.db_path, "audits")
        result = prepare_state_supervision_timeline_core_3a0_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertTrue(result.migrated)
        self.assertTrue(schema_is_present(self.db_path))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertEqual(_tables(self.db_path) - before, {TABLE_NAME})
        self.assertEqual(_count(self.db_path, TABLE_NAME), 0)
        self.assertEqual(_count(self.db_path, "state_supervisions"), supervisions_before)
        self.assertEqual(
            _count(self.db_path, "state_supervision_required_documents"),
            documents_before,
        )
        self.assertEqual(_count(self.db_path, "audits"), audits_before)
        self.assertTrue(REQUIRED_INDEXES.issubset(_indexes(self.db_path, TABLE_NAME)))
        columns = _index_columns(self.db_path, TABLE_NAME)
        indexed_cols = {col for cols in columns.values() for col in cols}
        self.assertNotIn("title", indexed_cols)
        self.assertNotIn("place", indexed_cols)
        self.assertNotIn("notes", indexed_cols)

    def test_04_idempotent_repeat(self) -> None:
        first = prepare_state_supervision_timeline_core_3a0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        backups_first = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertEqual(len(backups_first), 1)
        second = prepare_state_supervision_timeline_core_3a0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertFalse(second.migrated)
        backups_second = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertEqual(len(backups_second), 1)
        self.assertEqual(first.pre_migration_backup_path, backups_second[0])

    def test_05_previous_markers_unchanged(self) -> None:
        mark_migration_complete(
            self.ws, backup_path=None, transition_id=CORE1_TRANSITION_ID
        )
        mark_migration_complete(
            self.ws, backup_path=None, transition_id=DOCUMENTS_TRANSITION_ID
        )
        self.assertTrue(is_transition_complete(self.ws, CORE1_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, DOCUMENTS_TRANSITION_ID))
        prepare_state_supervision_timeline_core_3a0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertTrue(is_transition_complete(self.ws, CORE1_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, DOCUMENTS_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertNotEqual(TRANSITION_ID, CORE1_TRANSITION_ID)
        self.assertNotEqual(TRANSITION_ID, DOCUMENTS_TRANSITION_ID)
        self.assertEqual(CORE1_TRANSITION_ID, "state-supervision-core-1")
        self.assertEqual(DOCUMENTS_TRANSITION_ID, "state-supervision-documents-core-2c0")

    def test_06_ddl_failure_marks_failed(self) -> None:
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_timeline_core_3a0_schema_migration."
            "apply_state_supervision_timeline_core_3a0_schema_ddl",
            side_effect=RuntimeError("umělá chyba DDL"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_state_supervision_timeline_core_3a0_schema(
                    workspace_root=self.ws, database_path=self.db_path
                )
        self.assertTrue(is_migration_failed(self.ws, TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertTrue(needs_state_supervision_timeline_core_3a0_schema(self.db_path))

    def test_07_incomplete_blocks_prepare(self) -> None:
        mark_migration_in_progress(
            self.ws,
            backup_path=Path("/tmp/pre_state_supervision_timeline_fake.mbbackup"),
            transition_id=TRANSITION_ID,
        )
        with self.assertRaises(MigrationGuardError) as ctx:
            prepare_state_supervision_timeline_core_3a0_schema(
                workspace_root=self.ws, database_path=self.db_path
            )
        self.assertIn("nebyla dokončena", str(ctx.exception))
        self.assertNotIn(TABLE_NAME, _tables(self.db_path))

    def test_08_allocate_backup_name(self) -> None:
        path = allocate_state_supervision_timeline_core_3a0_backup_path(
            self.ws / "zalohy"
        )
        self.assertTrue(path.name.startswith(f"{BACKUP_NAME_PREFIX}_"))
        self.assertTrue(path.name.endswith(".mbbackup"))

    def test_09_upgrade_guard_wires_migration(self) -> None:
        source = inspect.getsource(prepare_database_for_startup)
        self.assertIn("needs_state_supervision_core_1_schema", source)
        self.assertIn("prepare_state_supervision_core_1_schema", source)
        self.assertGreaterEqual(
            source.count("prepare_state_supervision_core_1_schema("), 2
        )
        self.assertIn("needs_state_supervision_documents_core_2c0_schema", source)
        self.assertIn("prepare_state_supervision_documents_core_2c0_schema", source)
        self.assertGreaterEqual(
            source.count("prepare_state_supervision_documents_core_2c0_schema("), 2
        )
        self.assertIn("needs_state_supervision_timeline_core_3a0_schema", source)
        self.assertIn("prepare_state_supervision_timeline_core_3a0_schema", source)
        self.assertGreaterEqual(
            source.count("prepare_state_supervision_timeline_core_3a0_schema("), 2
        )


_SVC_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-timeline-3a0-svc-"))
with patch.object(Path, "home", return_value=_SVC_HOME):
    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.statni_dozor.constants import (
        STATUS_CANCELLED,
        STATUS_CLOSED,
        TABLE_TIMELINE_ITEMS,
    )
    from moduly.statni_dozor.modely.state_supervision_timeline_item_draft import (
        StateSupervisionTimelineItemDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_timeline_item_service import (
        StateSupervisionTimelineItemService,
        state_supervision_timeline_item_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )


class StateSupervisionTimelineCore3a0ServiceTestCase(unittest.TestCase):
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
        self.marker = uuid.uuid4().hex[:6]
        self.supervision = state_supervision_service.create_supervision(
            authority_name=f"OIP {self.marker}"
        )
        self.other = state_supervision_service.create_supervision(
            authority_name=f"KHS {self.marker}"
        )

    def test_01_clean_install_creates_table(self) -> None:
        db = storage_module.storage_service.database_path
        self.assertIn(TABLE_TIMELINE_ITEMS, _tables(db))
        self.assertTrue(REQUIRED_INDEXES.issubset(_indexes(db, TABLE_TIMELINE_ITEMS)))

    def test_02_draft_client_key_stable_before_parent_save(self) -> None:
        draft = StateSupervisionTimelineItemDraft(title="Zahájení kontroly")
        self.assertIsNone(draft.id)
        self.assertTrue(draft.client_key)
        key = draft.client_key
        draft.title = "Kontrola provozu vlečky"
        draft.place = "Vlečka"
        draft.display_order = 20
        draft.notes = "Poznámka"
        self.assertEqual(draft.client_key, key)
        other = StateSupervisionTimelineItemDraft(title="Jiný")
        self.assertNotEqual(draft.client_key, other.client_key)

    def test_03_create_one_and_several_in_order(self) -> None:
        first = state_supervision_timeline_item_service.create_timeline_item(
            self.supervision.id,
            title="Zahájení kontroly",
        )
        second = state_supervision_timeline_item_service.create_timeline_item(
            self.supervision.id,
            title="Kontrola provozu vlečky",
        )
        rows = state_supervision_timeline_item_service.list_timeline_items(
            self.supervision.id
        )
        self.assertEqual([row.id for row in rows], [first.id, second.id])
        self.assertEqual(rows[0].title, "Zahájení kontroly")
        self.assertLess(rows[0].display_order, rows[1].display_order)
        self.assertTrue(rows[0].active)

    def test_04_datetime_empty_place_and_czech_notes(self) -> None:
        notes = "Průběh:\nžluťoučký kůň\núpěl ďábelské ódy."
        occurred = datetime(2026, 4, 15, 9, 30, 0)
        future = datetime(2099, 1, 1, 8, 0, 0)
        past = datetime(2020, 12, 24, 11, 0, 0)
        with_time = state_supervision_timeline_item_service.create_timeline_item(
            self.supervision.id,
            title="Zahájení kontroly",
            occurred_at=occurred,
            place="Hala A",
            notes=notes,
        )
        empty = state_supervision_timeline_item_service.create_timeline_item(
            self.supervision.id,
            title="Doplněno zpětně",
            occurred_at=None,
            place="",
            notes="",
        )
        ahead = state_supervision_timeline_item_service.create_timeline_item(
            self.supervision.id,
            title="Připraveno dopředu",
            occurred_at=future,
        )
        back = state_supervision_timeline_item_service.create_timeline_item(
            self.supervision.id,
            title="Historický zápis",
            occurred_at=past,
        )
        self.assertEqual(with_time.occurred_at, occurred)
        self.assertEqual(with_time.place, "Hala A")
        self.assertEqual(with_time.notes, notes)
        self.assertIsNone(empty.occurred_at)
        self.assertIsNone(empty.place)
        self.assertIsNone(empty.notes)
        self.assertEqual(ahead.occurred_at, future)
        self.assertEqual(back.occurred_at, past)

    def test_05_validation(self) -> None:
        with self.assertRaises(StateSupervisionError):
            state_supervision_timeline_item_service.create_timeline_item(
                9_999_999,
                title="X",
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_timeline_item_service.create_timeline_item(
                self.supervision.id,
                title="   ",
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_timeline_item_service.create_timeline_item(
                self.supervision.id,
                title="X",
                display_order=-1,
            )

    def test_06_update_deactivate_reactivate_without_delete(self) -> None:
        row = state_supervision_timeline_item_service.create_timeline_item(
            self.supervision.id,
            title="Původní",
        )
        db = storage_module.storage_service.database_path
        before = _count(db, TABLE_TIMELINE_ITEMS)
        updated = state_supervision_timeline_item_service.update_timeline_item(
            row.id,
            title="Upravený",
            place="Dílna",
            notes="Zápisek",
        )
        self.assertEqual(updated.title, "Upravený")
        self.assertEqual(updated.place, "Dílna")
        deactivated = state_supervision_timeline_item_service.deactivate_timeline_item(
            row.id
        )
        self.assertFalse(deactivated.active)
        self.assertEqual(_count(db, TABLE_TIMELINE_ITEMS), before)
        active = state_supervision_timeline_item_service.list_timeline_items(
            self.supervision.id
        )
        self.assertEqual(active, [])
        history = state_supervision_timeline_item_service.list_timeline_items(
            self.supervision.id,
            include_inactive=True,
        )
        self.assertEqual(len(history), 1)
        reactivated = state_supervision_timeline_item_service.reactivate_timeline_item(
            row.id
        )
        self.assertTrue(reactivated.active)
        self.assertEqual(_count(db, TABLE_TIMELINE_ITEMS), before)

    def test_07_cannot_change_other_supervision_item(self) -> None:
        foreign = state_supervision_timeline_item_service.create_timeline_item(
            self.other.id,
            title="Cizí záznam",
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_timeline_item_service.save_timeline_batch(
                self.supervision.id,
                [
                    StateSupervisionTimelineItemDraft(
                        id=foreign.id,
                        title="Pokus o únos",
                    )
                ],
                deactivate_omitted=False,
            )
        loaded = state_supervision_timeline_item_service.get_timeline_item(foreign.id)
        self.assertEqual(loaded.title, "Cizí záznam")
        self.assertEqual(loaded.state_supervision_id, self.other.id)
        with self.assertRaises(StateSupervisionError):
            state_supervision_timeline_item_service.save_timeline_batch(
                self.supervision.id,
                [
                    StateSupervisionTimelineItemDraft(
                        id=foreign.id,
                        title="Cizí záznam",
                        active=False,
                    )
                ],
                deactivate_omitted=False,
            )
        still = state_supervision_timeline_item_service.get_timeline_item(foreign.id)
        self.assertTrue(still.active)
        self.assertEqual(still.title, "Cizí záznam")

    def test_08_batch_atomic_order_and_omitted_soft_delete(self) -> None:
        before = len(
            state_supervision_timeline_item_service.list_timeline_items(
                self.supervision.id, include_inactive=True
            )
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_timeline_item_service.save_timeline_batch(
                self.supervision.id,
                [
                    StateSupervisionTimelineItemDraft(title="Platný"),
                    StateSupervisionTimelineItemDraft(title="  "),
                ],
            )
        after_fail = state_supervision_timeline_item_service.list_timeline_items(
            self.supervision.id, include_inactive=True
        )
        self.assertEqual(len(after_fail), before)

        existing = state_supervision_timeline_item_service.create_timeline_item(
            self.supervision.id,
            title="Původní dávka",
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_timeline_item_service.save_timeline_batch(
                self.supervision.id,
                [
                    StateSupervisionTimelineItemDraft(
                        id=existing.id,
                        title="Nemá se uložit",
                    ),
                    StateSupervisionTimelineItemDraft(title=""),
                ],
            )
        reloaded = state_supervision_timeline_item_service.get_timeline_item(existing.id)
        self.assertEqual(reloaded.title, "Původní dávka")
        state_supervision_timeline_item_service.deactivate_timeline_item(existing.id)

        saved = state_supervision_timeline_item_service.save_timeline_batch(
            self.supervision.id,
            [
                StateSupervisionTimelineItemDraft(title="Druhý", display_order=5),
                StateSupervisionTimelineItemDraft(title="První", display_order=5),
                StateSupervisionTimelineItemDraft(title="Třetí", display_order=20),
            ],
            deactivate_omitted=False,
        )
        self.assertEqual([row.title for row in saved], ["Druhý", "První", "Třetí"])
        self.assertEqual([row.display_order for row in saved], [0, 10, 20])
        listed = state_supervision_timeline_item_service.list_timeline_items(
            self.supervision.id
        )
        self.assertEqual([row.title for row in listed], ["Druhý", "První", "Třetí"])

        kept = listed[1]
        omitted_batch = state_supervision_timeline_item_service.save_timeline_batch(
            self.supervision.id,
            [
                StateSupervisionTimelineItemDraft(
                    id=kept.id,
                    title=kept.title,
                    display_order=kept.display_order,
                )
            ],
        )
        self.assertEqual(len(omitted_batch), 1)
        active = state_supervision_timeline_item_service.list_timeline_items(
            self.supervision.id
        )
        self.assertEqual([row.title for row in active], ["První"])
        history = state_supervision_timeline_item_service.list_timeline_items(
            self.supervision.id,
            include_inactive=True,
        )
        hidden = [row for row in history if not row.active]
        self.assertGreaterEqual(len(hidden), 2)

        source = inspect.getsource(
            StateSupervisionTimelineItemService.save_timeline_batch
        )
        self.assertEqual(source.count("sess.commit()"), 1)
        self.assertNotIn("session.commit()", source)
        repo_source = inspect.getsource(
            type(state_supervision_timeline_item_service.repository).save_all
        )
        self.assertNotIn("sess.commit()", repo_source.split("for record in records")[0])
        public = [
            name
            for name in dir(StateSupervisionTimelineItemService)
            if not name.startswith("_")
        ]
        self.assertNotIn("delete", public)
        self.assertNotIn("delete_timeline_item", public)
        self.assertNotIn("remove", public)

    def test_09_closed_and_cancelled_keep_items(self) -> None:
        row = state_supervision_timeline_item_service.create_timeline_item(
            self.supervision.id,
            title="Zůstane",
        )
        state_supervision_service.update_supervision(
            self.supervision.id,
            status=STATUS_CLOSED,
        )
        listed = state_supervision_timeline_item_service.list_timeline_items(
            self.supervision.id
        )
        self.assertEqual(len(listed), 1)
        self.assertTrue(listed[0].active)
        self.assertEqual(listed[0].id, row.id)

        other_row = state_supervision_timeline_item_service.create_timeline_item(
            self.other.id,
            title="Zůstane po zrušení",
        )
        state_supervision_service.update_supervision(
            self.other.id,
            status=STATUS_CANCELLED,
        )
        cancelled = state_supervision_timeline_item_service.list_timeline_items(
            self.other.id
        )
        self.assertEqual(len(cancelled), 1)
        self.assertTrue(cancelled[0].active)
        self.assertEqual(cancelled[0].id, other_row.id)

    def test_10_ui_unchanged_two_editor_tabs(self) -> None:
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(source.count("self.tabs.addTab("), 2)
        self.assertNotIn("Průběh kontroly", source)
        self.assertNotIn("Závěr a opatření", source)
        self.assertNotIn("TimelineItem", source)
        self.assertNotIn("save_timeline_batch", source)
        bundle = inspect.getsource(
            StateSupervisionService.save_supervision_with_documents
        )
        self.assertNotIn("save_timeline_batch", bundle)
        self.assertNotIn("timeline", bundle.lower())
        from moduly.statni_dozor.ui import state_supervision_tab

        tab_source = inspect.getsource(state_supervision_tab)
        self.assertNotIn("save_timeline_batch", tab_source)
        self.assertNotIn("TimelineItem", tab_source)
        from moduly.agenda.ui import agenda_page

        agenda_source = inspect.getsource(agenda_page)
        self.assertIn("TAB_STATE_SUPERVISION", agenda_source)

    def test_11_incomplete_migration_blocks_startup(self) -> None:
        ws = storage_module.storage_service.base
        db = storage_module.storage_service.database_path
        prepare_database_for_startup(workspace_root=ws, database_path=db)
        state_before = read_migration_state(ws)
        try:
            mark_migration_in_progress(
                ws,
                backup_path=Path("/tmp/pre_state_supervision_timeline_fake.mbbackup"),
                transition_id=TRANSITION_ID,
            )
            with self.assertRaises(MigrationGuardError) as ctx:
                prepare_database_for_startup(
                    workspace_root=ws,
                    database_path=db,
                )
            self.assertIn("STATE-SUPERVISION-TIMELINE-CORE-3A0", str(ctx.exception))
        finally:
            write_migration_state(ws, state_before)


if __name__ == "__main__":
    unittest.main()
