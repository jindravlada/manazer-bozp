"""STATE-SUPERVISION-PARTICIPANTS-CORE-3C0: datový základ účastníků kontroly."""

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

from sqlalchemy.orm import Session

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


def _seed_pre_3c0_db(db_path: Path) -> None:
    """Existující DB s CORE-1, doklady 2C0 a průběhem 3A0, bez účastníků."""
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
                display_order INTEGER NOT NULL DEFAULT 0,
                active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(state_supervision_id) REFERENCES state_supervisions (id)
            );
            INSERT INTO state_supervision_required_documents (
                id, state_supervision_id, title, display_order, active
            ) VALUES (1, 1, 'Bezpečnostní listy', 0, 1);
            CREATE TABLE state_supervision_timeline_items (
                id INTEGER PRIMARY KEY,
                state_supervision_id INTEGER NOT NULL,
                title VARCHAR(250) NOT NULL,
                display_order INTEGER NOT NULL DEFAULT 0,
                active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(state_supervision_id) REFERENCES state_supervisions (id)
            );
            INSERT INTO state_supervision_timeline_items (
                id, state_supervision_id, title, display_order, active
            ) VALUES (1, 1, 'Zahájení kontroly', 0, 1);
            """
        )
        conn.commit()
    finally:
        conn.close()


REQUIRED_INDEXES = {
    "ix_state_supervision_participants_state_supervision_id",
    "ix_state_supervision_participants_list",
    "ix_state_supervision_participants_role",
    "ix_state_supervision_participants_source",
}

_MIG_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-participants-3c0-mig-"))
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
    TRANSITION_ID as TIMELINE_TRANSITION_ID,
)
from moduly.statni_dozor.sluzby.state_supervision_participants_core_3c0_schema_migration import (  # noqa: E402
    BACKUP_NAME_PREFIX,
    TABLE_NAME,
    TRANSITION_ID,
    allocate_state_supervision_participants_core_3c0_backup_path,
    needs_state_supervision_participants_core_3c0_schema,
    prepare_state_supervision_participants_core_3c0_schema,
    schema_is_present,
)

_MIG_HOME_PATCHER.stop()


class StateSupervisionParticipantsCore3c0MigrationTestCase(unittest.TestCase):
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
        _seed_pre_3c0_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_01_backup_before_ddl(self) -> None:
        result = prepare_state_supervision_participants_core_3c0_schema(
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
        self.assertIn(
            "pre_state_supervision_participants_",
            result.pre_migration_backup_path.name,
        )

    def test_02_backup_failure_no_table(self) -> None:
        before = _tables(self.db_path)
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_participants_core_3c0_schema_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_state_supervision_participants_core_3c0_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertTrue(
            needs_state_supervision_participants_core_3c0_schema(self.db_path)
        )
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
        timeline_before = _count(self.db_path, "state_supervision_timeline_items")
        audits_before = _count(self.db_path, "audits")
        result = prepare_state_supervision_participants_core_3c0_schema(
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
        self.assertEqual(
            _count(self.db_path, "state_supervision_timeline_items"),
            timeline_before,
        )
        self.assertEqual(_count(self.db_path, "audits"), audits_before)
        self.assertTrue(REQUIRED_INDEXES.issubset(_indexes(self.db_path, TABLE_NAME)))
        columns = _index_columns(self.db_path, TABLE_NAME)
        indexed_cols = {col for cols in columns.values() for col in cols}
        self.assertNotIn("name_snapshot", indexed_cols)
        self.assertNotIn("organization_snapshot", indexed_cols)
        self.assertNotIn("contact_note", indexed_cols)
        self.assertNotIn("note", indexed_cols)

    def test_04_idempotent_repeat(self) -> None:
        first = prepare_state_supervision_participants_core_3c0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        backups_first = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertEqual(len(backups_first), 1)
        second = prepare_state_supervision_participants_core_3c0_schema(
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
        mark_migration_complete(
            self.ws, backup_path=None, transition_id=TIMELINE_TRANSITION_ID
        )
        prepare_state_supervision_participants_core_3c0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertTrue(is_transition_complete(self.ws, CORE1_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, DOCUMENTS_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, TIMELINE_TRANSITION_ID))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertEqual(CORE1_TRANSITION_ID, "state-supervision-core-1")
        self.assertEqual(DOCUMENTS_TRANSITION_ID, "state-supervision-documents-core-2c0")
        self.assertEqual(TIMELINE_TRANSITION_ID, "state-supervision-timeline-core-3a0")
        self.assertEqual(TRANSITION_ID, "state-supervision-participants-core-3c0")

    def test_06_ddl_failure_marks_failed(self) -> None:
        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_participants_core_3c0_schema_migration."
            "apply_state_supervision_participants_core_3c0_schema_ddl",
            side_effect=RuntimeError("umělá chyba DDL"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_state_supervision_participants_core_3c0_schema(
                    workspace_root=self.ws, database_path=self.db_path
                )
        self.assertTrue(is_migration_failed(self.ws, TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertTrue(
            needs_state_supervision_participants_core_3c0_schema(self.db_path)
        )

    def test_07_incomplete_blocks_prepare(self) -> None:
        mark_migration_in_progress(
            self.ws,
            backup_path=Path("/tmp/pre_state_supervision_participants_fake.mbbackup"),
            transition_id=TRANSITION_ID,
        )
        with self.assertRaises(MigrationGuardError) as ctx:
            prepare_state_supervision_participants_core_3c0_schema(
                workspace_root=self.ws, database_path=self.db_path
            )
        self.assertIn("nebyla dokončena", str(ctx.exception))
        self.assertNotIn(TABLE_NAME, _tables(self.db_path))

    def test_08_allocate_backup_name(self) -> None:
        path = allocate_state_supervision_participants_core_3c0_backup_path(
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
        self.assertGreaterEqual(
            source.count("prepare_state_supervision_documents_core_2c0_schema("), 2
        )
        self.assertIn("needs_state_supervision_timeline_core_3a0_schema", source)
        self.assertGreaterEqual(
            source.count("prepare_state_supervision_timeline_core_3a0_schema("), 2
        )
        self.assertIn("needs_state_supervision_participants_core_3c0_schema", source)
        self.assertIn("prepare_state_supervision_participants_core_3c0_schema", source)
        self.assertGreaterEqual(
            source.count("prepare_state_supervision_participants_core_3c0_schema("), 2
        )


_SVC_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-participants-3c0-svc-"))
with patch.object(Path, "home", return_value=_SVC_HOME):
    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from core.database.session import get_session
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        ATTENDANCE_ABSENT,
        ATTENDANCE_ATTENDED,
        PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE,
        PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE,
        PARTICIPANT_ROLE_INSPECTOR,
        PARTICIPANT_ROLE_MANAGEMENT,
        PARTICIPANT_ROLE_OTHER,
        PARTICIPANT_ROLE_SPECIALIST,
        PARTICIPANT_ROLE_TRADE_UNION,
        PARTICIPANT_ROLES,
        PARTICIPANT_SOURCE_PERSON,
        PARTICIPANT_SOURCE_THP_WORKER,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
        TABLE_PARTICIPANTS,
    )
    from moduly.statni_dozor.modely.state_supervision_participant_draft import (
        StateSupervisionParticipantDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_participant_service import (
        StateSupervisionParticipantService,
        state_supervision_participant_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )


class StateSupervisionParticipantsCore3c0ServiceTestCase(unittest.TestCase):
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
        self.assertIn(TABLE_PARTICIPANTS, _tables(db))
        self.assertTrue(REQUIRED_INDEXES.issubset(_indexes(db, TABLE_PARTICIPANTS)))

    def test_02_draft_client_key_stable(self) -> None:
        draft = StateSupervisionParticipantDraft(
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Ing. Novák",
        )
        self.assertIsNone(draft.id)
        self.assertTrue(draft.client_key)
        key = draft.client_key
        draft.name_snapshot = "Ing. Novák st."
        draft.display_order = 20
        self.assertEqual(draft.client_key, key)
        other = StateSupervisionParticipantDraft(
            role=PARTICIPANT_ROLE_OTHER,
            name_snapshot="Jiný",
        )
        self.assertNotEqual(draft.client_key, other.client_key)

    def test_03_external_inspector_and_all_roles(self) -> None:
        row = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Ing. Karel Novák",
            organization_snapshot="OIP Praha",
            contact_note="novak@oip.example",
        )
        self.assertEqual(row.role, PARTICIPANT_ROLE_INSPECTOR)
        self.assertEqual(row.name_snapshot, "Ing. Karel Novák")
        self.assertEqual(row.organization_snapshot, "OIP Praha")
        self.assertIsNone(row.source_type)
        self.assertIsNone(row.source_id)
        self.assertTrue(row.planned)
        self.assertIsNone(row.attendance_status)
        self.assertTrue(row.active)

        for role in PARTICIPANT_ROLES:
            created = state_supervision_participant_service.create_participant(
                self.other.id,
                role=role,
                name_snapshot=f"Účastník {role}",
            )
            self.assertEqual(created.role, role)

    def test_04_catalog_person_and_thp_snapshot_survives_rename(self) -> None:
        person_row = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE,
            source_type=PARTICIPANT_SOURCE_PERSON,
            source_id=self.person.id,
            organization_snapshot="Zaměstnavatel",
        )
        self.assertEqual(person_row.source_type, PARTICIPANT_SOURCE_PERSON)
        original_person = person_row.name_snapshot
        self.assertIn("Jana", original_person or "")

        thp_row = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_SPECIALIST,
            source_type=PARTICIPANT_SOURCE_THP_WORKER,
            source_id=self.worker.id,
        )
        original_thp = thp_row.name_snapshot
        self.assertIn("Petr", original_thp or "")

        person_service.update_person(
            self.person.id,
            first_name="Jana",
            last_name=f"Přejmenovaná-{self.marker}",
            active=False,
        )
        settings_service.save_worker(
            id=self.worker.id,
            first_name="Petr",
            last_name=f"Nový-{self.marker}",
        )
        reloaded_person = state_supervision_participant_service.get_participant(
            person_row.id
        )
        reloaded_thp = state_supervision_participant_service.get_participant(thp_row.id)
        self.assertEqual(reloaded_person.name_snapshot, original_person)
        self.assertEqual(reloaded_thp.name_snapshot, original_thp)
        updated = state_supervision_participant_service.update_participant(
            person_row.id,
            attendance_status=ATTENDANCE_ATTENDED,
        )
        self.assertEqual(updated.name_snapshot, original_person)
        self.assertEqual(updated.organization_snapshot, "Zaměstnavatel")

    def test_05_reject_source_role_name_and_attendance(self) -> None:
        with self.assertRaises(StateSupervisionError):
            state_supervision_participant_service.create_participant(
                self.supervision.id,
                role=PARTICIPANT_ROLE_INSPECTOR,
                source_type="contractor",
                source_id=1,
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_participant_service.create_participant(
                self.supervision.id,
                role=PARTICIPANT_ROLE_INSPECTOR,
                source_type=PARTICIPANT_SOURCE_PERSON,
                source_id=None,
                name_snapshot="Bez ID",
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_participant_service.create_participant(
                self.supervision.id,
                role=PARTICIPANT_ROLE_INSPECTOR,
                source_type=None,
                source_id=self.person.id,
                name_snapshot="Bez typu",
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_participant_service.create_participant(
                self.supervision.id,
                role=PARTICIPANT_ROLE_INSPECTOR,
                name_snapshot="   ",
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_participant_service.create_participant(
                self.supervision.id,
                role="witness",
                name_snapshot="Svědek",
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_participant_service.create_participant(
                self.supervision.id,
                role=PARTICIPANT_ROLE_INSPECTOR,
                name_snapshot="X",
                attendance_status="late",
            )
        with self.assertRaises(StateSupervisionError):
            state_supervision_participant_service.create_participant(
                9_999_999,
                role=PARTICIPANT_ROLE_INSPECTOR,
                name_snapshot="X",
            )

    def test_06_planned_attendance_and_czech_note(self) -> None:
        note = "Účast:\nžluťoučký kůň\núpěl ďábelské ódy."
        planned = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_MANAGEMENT,
            name_snapshot="Ředitel",
            planned=True,
            attendance_status=None,
            note=note,
        )
        unplanned = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_TRADE_UNION,
            name_snapshot="Odbory",
            planned=False,
            attendance_status=ATTENDANCE_ABSENT,
        )
        self.assertTrue(planned.planned)
        self.assertIsNone(planned.attendance_status)
        self.assertEqual(planned.note, note)
        self.assertFalse(unplanned.planned)
        self.assertEqual(unplanned.attendance_status, ATTENDANCE_ABSENT)
        attended = state_supervision_participant_service.update_participant(
            planned.id,
            attendance_status=ATTENDANCE_ATTENDED,
        )
        self.assertEqual(attended.attendance_status, ATTENDANCE_ATTENDED)
        cleared = state_supervision_participant_service.update_participant(
            planned.id,
            attendance_status="",
        )
        self.assertIsNone(cleared.attendance_status)

    def test_07_order_normalization_and_single_update_keeps_others(self) -> None:
        first = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="První",
        )
        second = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_OTHER,
            name_snapshot="Druhý",
        )
        self.assertLess(first.display_order, second.display_order)
        original_second = second.display_order
        state_supervision_participant_service.update_participant(
            first.id,
            name_snapshot="První upravený",
        )
        reloaded_second = state_supervision_participant_service.get_participant(
            second.id
        )
        self.assertEqual(reloaded_second.display_order, original_second)

        saved = state_supervision_participant_service.save_participant_batch(
            self.supervision.id,
            [
                StateSupervisionParticipantDraft(
                    role=PARTICIPANT_ROLE_INSPECTOR,
                    name_snapshot="B",
                    display_order=5,
                ),
                StateSupervisionParticipantDraft(
                    role=PARTICIPANT_ROLE_OTHER,
                    name_snapshot="A",
                    display_order=5,
                ),
                StateSupervisionParticipantDraft(
                    role=PARTICIPANT_ROLE_SPECIALIST,
                    name_snapshot="C",
                    display_order=20,
                ),
            ],
            deactivate_omitted=False,
        )
        self.assertEqual([row.name_snapshot for row in saved], ["B", "A", "C"])
        self.assertEqual([row.display_order for row in saved], [0, 10, 20])

    def test_08_foreign_id_atomic_rollback_and_caller_owned_session(self) -> None:
        foreign = state_supervision_participant_service.create_participant(
            self.other.id,
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Cizí",
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_participant_service.save_participant_batch(
                self.supervision.id,
                [
                    StateSupervisionParticipantDraft(
                        id=foreign.id,
                        role=PARTICIPANT_ROLE_INSPECTOR,
                        name_snapshot="Pokus o únos",
                    )
                ],
                deactivate_omitted=False,
            )
        loaded = state_supervision_participant_service.get_participant(foreign.id)
        self.assertEqual(loaded.name_snapshot, "Cizí")
        self.assertEqual(loaded.state_supervision_id, self.other.id)

        before = len(
            state_supervision_participant_service.list_participants(
                self.supervision.id, include_inactive=True
            )
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_participant_service.save_participant_batch(
                self.supervision.id,
                [
                    StateSupervisionParticipantDraft(
                        role=PARTICIPANT_ROLE_INSPECTOR,
                        name_snapshot="Platný",
                    ),
                    StateSupervisionParticipantDraft(
                        role=PARTICIPANT_ROLE_INSPECTOR,
                        name_snapshot="  ",
                    ),
                ],
            )
        after_fail = state_supervision_participant_service.list_participants(
            self.supervision.id, include_inactive=True
        )
        self.assertEqual(len(after_fail), before)

        sess = get_session()
        try:
            with patch.object(Session, "commit") as commit:
                state_supervision_participant_service.save_participant_batch(
                    self.supervision.id,
                    [
                        StateSupervisionParticipantDraft(
                            role=PARTICIPANT_ROLE_INSPECTOR,
                            name_snapshot="Jen flush",
                        )
                    ],
                    session=sess,
                    deactivate_omitted=False,
                )
                commit.assert_not_called()
            sess.rollback()
        finally:
            sess.close()
        self.assertEqual(
            [
                row.name_snapshot
                for row in state_supervision_participant_service.list_participants(
                    self.supervision.id
                )
            ],
            [],
        )

    def test_09_soft_delete_history_reactivate_and_closed_keeps(self) -> None:
        row = state_supervision_participant_service.create_participant(
            self.supervision.id,
            role=PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE,
            name_snapshot="Zmocněnec",
        )
        db = storage_module.storage_service.database_path
        before = _count(db, TABLE_PARTICIPANTS)
        deactivated = state_supervision_participant_service.deactivate_participant(
            row.id
        )
        self.assertFalse(deactivated.active)
        self.assertEqual(_count(db, TABLE_PARTICIPANTS), before)
        self.assertEqual(
            state_supervision_participant_service.list_participants(
                self.supervision.id
            ),
            [],
        )
        history = state_supervision_participant_service.list_participants(
            self.supervision.id,
            include_inactive=True,
        )
        self.assertEqual(len(history), 1)
        reactivated = state_supervision_participant_service.reactivate_participant(
            row.id
        )
        self.assertTrue(reactivated.active)

        started = datetime(2026, 3, 1, 8, 0, 0)
        ended = datetime(2026, 3, 1, 16, 0, 0)
        state_supervision_service.update_supervision(
            self.supervision.id,
            started_at=started,
            ended_at=ended,
            status="in_progress",
        )
        state_supervision_participant_service.update_participant(
            row.id,
            attendance_status=ATTENDANCE_ATTENDED,
        )
        supervision = state_supervision_service.get_supervision(self.supervision.id)
        self.assertEqual(supervision.status, "in_progress")
        self.assertEqual(supervision.started_at, started)
        self.assertEqual(supervision.ended_at, ended)

        state_supervision_service.update_supervision(
            self.supervision.id,
            status=STATUS_CLOSED,
            closed_at=datetime(2026, 5, 1, 12, 0),
        )
        listed = state_supervision_participant_service.list_participants(
            self.supervision.id
        )
        self.assertEqual(len(listed), 1)
        self.assertTrue(listed[0].active)

        other_row = state_supervision_participant_service.create_participant(
            self.other.id,
            role=PARTICIPANT_ROLE_OTHER,
            name_snapshot="Po zrušení",
        )
        state_supervision_service.update_supervision(
            self.other.id,
            status=STATUS_CANCELLED,
        )
        cancelled = state_supervision_participant_service.list_participants(
            self.other.id
        )
        self.assertEqual(len(cancelled), 1)
        self.assertEqual(cancelled[0].id, other_row.id)

    def test_10_no_delete_no_bundle_hook_four_tabs_no_write_on_open(self) -> None:
        public = [
            name
            for name in dir(StateSupervisionParticipantService)
            if not name.startswith("_")
        ]
        self.assertNotIn("delete", public)
        self.assertNotIn("delete_participant", public)
        self.assertNotIn("remove", public)
        batch_source = inspect.getsource(
            StateSupervisionParticipantService.save_participant_batch
        )
        self.assertEqual(batch_source.count("sess.commit()"), 1)
        self.assertNotIn("session.commit()", batch_source)
        bundle = inspect.getsource(StateSupervisionService.save_supervision_bundle)
        self.assertIn("save_participant_batch", bundle)
        self.assertIn("participants", bundle)
        self.assertIn("KEEP_EXISTING", bundle)
        self.assertEqual(bundle.count("sess.commit()"), 1)
        editor_source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(editor_source.count("self.tabs.addTab("), 5)
        self.assertNotIn("TAB_PARTICIPANTS", editor_source)
        self.assertNotIn("save_participant_batch", editor_source)

        db = storage_module.storage_service.database_path
        before = _count(db, TABLE_PARTICIPANTS)
        dialog = StateSupervisionEditorDialog(supervision_id=self.supervision.id)
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
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()
        self.assertEqual(_count(db, TABLE_PARTICIPANTS), before)

        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        page.close()

    def test_11_incomplete_migration_blocks_startup(self) -> None:
        ws = storage_module.storage_service.base
        db = storage_module.storage_service.database_path
        prepare_database_for_startup(workspace_root=ws, database_path=db)
        state_before = read_migration_state(ws)
        try:
            mark_migration_in_progress(
                ws,
                backup_path=Path(
                    "/tmp/pre_state_supervision_participants_fake.mbbackup"
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
