"""STATE-SUPERVISION-DOCUMENTS-CORE-2C0: datový základ požadovaných dokladů."""

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


def _seed_pre_2c0_db(db_path: Path) -> None:
    """Existující DB s kontrolami CORE-1, bez tabulky dokladů."""
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
            """
        )
        conn.commit()
    finally:
        conn.close()


REQUIRED_INDEXES = {
    "ix_state_supervision_required_documents_state_supervision_id",
    "ix_state_supervision_required_documents_list",
    "ix_state_supervision_required_documents_due_at",
}

_MIG_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-docs-2c0-mig-"))
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
    BACKUP_NAME_PREFIX,
    TABLE_NAME,
    TRANSITION_ID,
    allocate_state_supervision_documents_core_2c0_backup_path,
    needs_state_supervision_documents_core_2c0_schema,
    prepare_state_supervision_documents_core_2c0_schema,
    schema_is_present,
)

_MIG_HOME_PATCHER.stop()


class StateSupervisionDocumentsCore2c0MigrationTestCase(unittest.TestCase):
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
        _seed_pre_2c0_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_01_backup_before_ddl(self) -> None:
        result = prepare_state_supervision_documents_core_2c0_schema(
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
            "moduly.statni_dozor.sluzby.state_supervision_documents_core_2c0_schema_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_state_supervision_documents_core_2c0_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertTrue(needs_state_supervision_documents_core_2c0_schema(self.db_path))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.ws, TRANSITION_ID))
        self.assertEqual(_tables(self.db_path), before)
        self.assertNotIn(TABLE_NAME, before)

    def test_03_successful_additive_no_backfill(self) -> None:
        before = _tables(self.db_path)
        supervisions_before = _count(self.db_path, "state_supervisions")
        audits_before = _count(self.db_path, "audits")
        result = prepare_state_supervision_documents_core_2c0_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertTrue(result.migrated)
        self.assertTrue(schema_is_present(self.db_path))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertEqual(_tables(self.db_path) - before, {TABLE_NAME})
        self.assertEqual(_count(self.db_path, TABLE_NAME), 0)
        self.assertEqual(_count(self.db_path, "state_supervisions"), supervisions_before)
        self.assertEqual(_count(self.db_path, "audits"), audits_before)
        self.assertTrue(REQUIRED_INDEXES.issubset(_indexes(self.db_path, TABLE_NAME)))

    def test_04_idempotent_repeat(self) -> None:
        first = prepare_state_supervision_documents_core_2c0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        backups_first = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertEqual(len(backups_first), 1)
        second = prepare_state_supervision_documents_core_2c0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertFalse(second.migrated)
        backups_second = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertEqual(len(backups_second), 1)
        self.assertEqual(first.pre_migration_backup_path, backups_second[0])

    def test_05_core1_marker_unchanged(self) -> None:
        mark_migration_complete(
            self.ws, backup_path=None, transition_id=CORE1_TRANSITION_ID
        )
        self.assertTrue(is_transition_complete(self.ws, CORE1_TRANSITION_ID))
        prepare_state_supervision_documents_core_2c0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertTrue(is_transition_complete(self.ws, CORE1_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertNotEqual(TRANSITION_ID, CORE1_TRANSITION_ID)

    def test_06_ddl_failure_marks_failed(self) -> None:
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_documents_core_2c0_schema_migration."
            "apply_state_supervision_documents_core_2c0_schema_ddl",
            side_effect=RuntimeError("umělá chyba DDL"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_state_supervision_documents_core_2c0_schema(
                    workspace_root=self.ws, database_path=self.db_path
                )
        self.assertTrue(is_migration_failed(self.ws, TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertTrue(needs_state_supervision_documents_core_2c0_schema(self.db_path))

    def test_07_incomplete_blocks_prepare(self) -> None:
        mark_migration_in_progress(
            self.ws,
            backup_path=Path("/tmp/pre_state_supervision_documents_fake.mbbackup"),
            transition_id=TRANSITION_ID,
        )
        with self.assertRaises(MigrationGuardError) as ctx:
            prepare_state_supervision_documents_core_2c0_schema(
                workspace_root=self.ws, database_path=self.db_path
            )
        self.assertIn("nebyla dokončena", str(ctx.exception))
        self.assertNotIn(TABLE_NAME, _tables(self.db_path))

    def test_08_allocate_backup_name(self) -> None:
        path = allocate_state_supervision_documents_core_2c0_backup_path(
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


_SVC_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-docs-2c0-svc-"))
with patch.object(Path, "home", return_value=_SVC_HOME):
    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.statni_dozor.constants import (
        RESPONSIBLE_SOURCE_PERSON,
        RESPONSIBLE_SOURCE_THP_WORKER,
        STATUS_CLOSED,
        TABLE_REQUIRED_DOCUMENTS,
    )
    from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
        StateSupervisionRequiredDocumentDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        StateSupervisionRequiredDocumentService,
        state_supervision_required_document_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )


class StateSupervisionDocumentsCore2c0ServiceTestCase(unittest.TestCase):
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
        self.person = person_service.create_person(
            first_name="Jana",
            last_name=f"Osoba-{self.marker}",
        )
        self.worker = settings_service.save_worker(
            first_name="Petr",
            last_name=f"THP-{self.marker}",
        )

    def test_01_clean_install_creates_table(self) -> None:
        db = storage_module.storage_service.database_path
        self.assertIn(TABLE_REQUIRED_DOCUMENTS, _tables(db))
        self.assertTrue(
            REQUIRED_INDEXES.issubset(_indexes(db, TABLE_REQUIRED_DOCUMENTS))
        )

    def test_02_create_one_and_list_order(self) -> None:
        first = state_supervision_required_document_service.create_document(
            self.supervision.id,
            title="Bezpečnostní listy",
        )
        second = state_supervision_required_document_service.create_document(
            self.supervision.id,
            title="Prezenční listiny",
        )
        rows = state_supervision_required_document_service.list_documents(
            self.supervision.id
        )
        self.assertEqual([row.id for row in rows], [first.id, second.id])
        self.assertEqual(rows[0].title, "Bezpečnostní listy")
        self.assertLess(rows[0].display_order, rows[1].display_order)
        self.assertTrue(rows[0].active)

    def test_03_czech_multiline_optional_dates_and_flags(self) -> None:
        text = "Doklad:\nžluťoučký kůň\núpěl ďábelské ódy."
        prepared = datetime(2026, 3, 1, 9, 0, 0)
        submitted = datetime(2026, 3, 2, 14, 30, 0)
        row = state_supervision_required_document_service.create_document(
            self.supervision.id,
            title=text,
            note=text,
            due_at=None,
            prepared_at=prepared,
            submitted_at=submitted,
        )
        self.assertEqual(row.title, text)
        self.assertEqual(row.note, text)
        self.assertIsNone(row.due_at)
        self.assertEqual(row.prepared_at, prepared)
        self.assertEqual(row.submitted_at, submitted)
        self.assertIsNone(row.responsible_source_type)

    def test_04_person_and_thp_snapshot_survives_rename(self) -> None:
        person_row = state_supervision_required_document_service.create_document(
            self.supervision.id,
            title="Osoba",
            responsible_source_type=RESPONSIBLE_SOURCE_PERSON,
            responsible_source_id=self.person.id,
        )
        self.assertEqual(person_row.responsible_source_type, RESPONSIBLE_SOURCE_PERSON)
        original_person = person_row.responsible_name_snapshot
        self.assertIn("Jana", original_person or "")

        thp_row = state_supervision_required_document_service.create_document(
            self.supervision.id,
            title="THP",
            responsible_source_type=RESPONSIBLE_SOURCE_THP_WORKER,
            responsible_source_id=self.worker.id,
        )
        original_thp = thp_row.responsible_name_snapshot
        self.assertIn("Petr", original_thp or "")

        person_service.update_person(
            self.person.id,
            first_name="Jana",
            last_name=f"Přejmenovaná-{self.marker}",
        )
        settings_service.save_worker(
            id=self.worker.id,
            first_name="Petr",
            last_name=f"Nový-{self.marker}",
        )
        person_service.update_person(
            self.person.id,
            first_name="Jana",
            last_name=f"Přejmenovaná-{self.marker}",
            active=False,
        )

        reloaded_person = state_supervision_required_document_service.get_document(
            person_row.id
        )
        reloaded_thp = state_supervision_required_document_service.get_document(
            thp_row.id
        )
        self.assertEqual(reloaded_person.responsible_name_snapshot, original_person)
        self.assertEqual(reloaded_thp.responsible_name_snapshot, original_thp)

        updated = state_supervision_required_document_service.update_document(
            person_row.id,
            title="Osoba upravena",
        )
        self.assertEqual(updated.responsible_name_snapshot, original_person)

    def test_05_reject_unknown_and_incomplete_person(self) -> None:
        with self.assertRaises(StateSupervisionError):
            state_supervision_required_document_service.create_document(
                self.supervision.id,
                title="X",
                responsible_source_type="contractor",
                responsible_source_id=1,
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_required_document_service.create_document(
                self.supervision.id,
                title="X",
                responsible_source_type=RESPONSIBLE_SOURCE_PERSON,
                responsible_source_id=None,
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_required_document_service.create_document(
                self.supervision.id,
                title="X",
                responsible_source_type=None,
                responsible_source_id=self.person.id,
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_required_document_service.create_document(
                9_999_999,
                title="X",
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_required_document_service.create_document(
                self.supervision.id,
                title="   ",
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_required_document_service.create_document(
                self.supervision.id,
                title="X",
                display_order=-1,
            )

    def test_06_update_deactivate_reactivate_without_delete(self) -> None:
        row = state_supervision_required_document_service.create_document(
            self.supervision.id,
            title="Původní",
        )
        db = storage_module.storage_service.database_path
        before = _count(db, TABLE_REQUIRED_DOCUMENTS)
        updated = state_supervision_required_document_service.update_document(
            row.id,
            title="Upravený",
            note="Poznámka",
        )
        self.assertEqual(updated.title, "Upravený")
        deactivated = state_supervision_required_document_service.deactivate_document(
            row.id
        )
        self.assertFalse(deactivated.active)
        self.assertEqual(_count(db, TABLE_REQUIRED_DOCUMENTS), before)
        active = state_supervision_required_document_service.list_documents(
            self.supervision.id
        )
        self.assertEqual(active, [])
        history = state_supervision_required_document_service.list_documents(
            self.supervision.id,
            include_inactive=True,
        )
        self.assertEqual(len(history), 1)
        reactivated = state_supervision_required_document_service.reactivate_document(
            row.id
        )
        self.assertTrue(reactivated.active)
        self.assertEqual(_count(db, TABLE_REQUIRED_DOCUMENTS), before)

    def test_07_cannot_change_other_supervision_document(self) -> None:
        foreign = state_supervision_required_document_service.create_document(
            self.other.id,
            title="Cizí doklad",
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_required_document_service.save_document_batch(
                self.supervision.id,
                [
                    StateSupervisionRequiredDocumentDraft(
                        id=foreign.id,
                        title="Pokus o únos",
                    )
                ],
            )
        loaded = state_supervision_required_document_service.get_document(foreign.id)
        self.assertEqual(loaded.title, "Cizí doklad")
        self.assertEqual(loaded.state_supervision_id, self.other.id)

    def test_08_batch_atomic_and_order_normalization(self) -> None:
        before = len(
            state_supervision_required_document_service.list_documents(
                self.supervision.id, include_inactive=True
            )
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_required_document_service.save_document_batch(
                self.supervision.id,
                [
                    StateSupervisionRequiredDocumentDraft(title="Platný"),
                    StateSupervisionRequiredDocumentDraft(title="  "),
                ],
            )
        after_fail = state_supervision_required_document_service.list_documents(
            self.supervision.id, include_inactive=True
        )
        self.assertEqual(len(after_fail), before)

        existing = state_supervision_required_document_service.create_document(
            self.supervision.id,
            title="Původní dávka",
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_required_document_service.save_document_batch(
                self.supervision.id,
                [
                    StateSupervisionRequiredDocumentDraft(
                        id=existing.id,
                        title="Nemá se uložit",
                    ),
                    StateSupervisionRequiredDocumentDraft(title=""),
                ],
            )
        reloaded = state_supervision_required_document_service.get_document(existing.id)
        self.assertEqual(reloaded.title, "Původní dávka")
        state_supervision_required_document_service.deactivate_document(existing.id)

        saved = state_supervision_required_document_service.save_document_batch(
            self.supervision.id,
            [
                StateSupervisionRequiredDocumentDraft(title="Druhý", display_order=5),
                StateSupervisionRequiredDocumentDraft(title="První", display_order=5),
                StateSupervisionRequiredDocumentDraft(title="Třetí", display_order=20),
            ],
        )
        self.assertEqual([row.title for row in saved], ["Druhý", "První", "Třetí"])
        self.assertEqual([row.display_order for row in saved], [0, 10, 20])
        listed = state_supervision_required_document_service.list_documents(
            self.supervision.id
        )
        self.assertEqual([row.title for row in listed], ["Druhý", "První", "Třetí"])

        source = inspect.getsource(
            StateSupervisionRequiredDocumentService.save_document_batch
        )
        self.assertEqual(source.count("sess.commit()"), 1)
        self.assertNotIn("session.commit()", source)
        public = [
            name
            for name in dir(StateSupervisionRequiredDocumentService)
            if not name.startswith("_")
        ]
        self.assertNotIn("delete", public)
        self.assertNotIn("delete_document", public)
        self.assertNotIn("remove", public)

    def test_09_closed_supervision_keeps_documents(self) -> None:
        row = state_supervision_required_document_service.create_document(
            self.supervision.id,
            title="Zůstane",
        )
        state_supervision_service.update_supervision(
            self.supervision.id,
            status=STATUS_CLOSED,
        )
        listed = state_supervision_required_document_service.list_documents(
            self.supervision.id
        )
        self.assertEqual(len(listed), 1)
        self.assertTrue(listed[0].active)
        self.assertEqual(listed[0].id, row.id)

    def test_10_editor_still_two_tabs_without_delete(self) -> None:
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(source.count("self.tabs.addTab("), 2)
        self.assertNotIn("Průběh kontroly", source)
        self.assertNotIn("Závěr a opatření", source)
        public = [
            name
            for name in dir(type(state_supervision_required_document_service))
            if not name.startswith("_")
        ]
        self.assertNotIn("delete_document", public)
        from moduly.statni_dozor.ui import state_supervision_tab

        tab_source = inspect.getsource(state_supervision_tab)
        self.assertNotIn("save_document_batch", tab_source)

    def test_11_incomplete_migration_blocks_startup(self) -> None:
        ws = storage_module.storage_service.base
        db = storage_module.storage_service.database_path
        prepare_database_for_startup(workspace_root=ws, database_path=db)
        state_before = read_migration_state(ws)
        try:
            mark_migration_in_progress(
                ws,
                backup_path=Path("/tmp/pre_state_supervision_documents_fake.mbbackup"),
                transition_id=TRANSITION_ID,
            )
            with self.assertRaises(MigrationGuardError) as ctx:
                prepare_database_for_startup(
                    workspace_root=ws,
                    database_path=db,
                )
            self.assertIn("STATE-SUPERVISION-DOCUMENTS-CORE-2C0", str(ctx.exception))
        finally:
            write_migration_state(ws, state_before)


if __name__ == "__main__":
    unittest.main()
