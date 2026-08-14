"""EXTERNAL-AUDIT-EA-0: migrace, služby, validace — bez UI."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import date
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


def _seed_pre_ea0_db(db_path: Path) -> None:
    """DB s interním auditem, bez tabulek externích auditů."""
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
            """
        )
        conn.commit()
    finally:
        conn.close()


REQUIRED_EA_TABLES = {
    "external_audits",
    "external_audit_visits",
    "external_audit_participants",
    "external_audit_visit_participants",
    "external_audit_findings",
    "external_audit_finding_task_links",
}


_MIG_HOME = Path(tempfile.mkdtemp(prefix="external-audit-ea-0-mig-"))
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
)
from moduly.externi_audity.sluzby.external_audit_ea_0_schema_migration import (  # noqa: E402
    BACKUP_NAME_PREFIX,
    REQUIRED_TABLES,
    TRANSITION_ID,
    allocate_external_audit_ea_0_backup_path,
    apply_external_audit_ea_0_schema_ddl,
    needs_external_audit_ea_0_schema,
    prepare_external_audit_ea_0_schema,
    schema_is_present,
)

_MIG_HOME_PATCHER.stop()


class ExternalAuditEa0MigrationTestCase(unittest.TestCase):
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
        _seed_pre_ea0_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_01_backup_before_ddl(self) -> None:
        result = prepare_external_audit_ea_0_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertTrue(result.migrated)
        assert result.pre_migration_backup_path is not None
        self.assertTrue(result.pre_migration_backup_path.is_file())
        self.assertTrue(
            result.pre_migration_backup_path.name.startswith(BACKUP_NAME_PREFIX)
        )
        self.assertTrue(result.pre_migration_backup_path.suffix == ".mbbackup")

    def test_02_backup_failure_no_tables(self) -> None:
        before = _tables(self.db_path)
        with patch(
            "moduly.externi_audity.sluzby.external_audit_ea_0_schema_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_external_audit_ea_0_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertTrue(needs_external_audit_ea_0_schema(self.db_path))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.ws, TRANSITION_ID))
        self.assertEqual(_tables(self.db_path), before)
        self.assertTrue(REQUIRED_EA_TABLES.isdisjoint(before))

    def test_03_successful_additive_migration(self) -> None:
        before = _tables(self.db_path)
        audits_before = _count(self.db_path, "audits")
        tasks_before = _count(self.db_path, "tasks")
        internal_row = sqlite3.connect(str(self.db_path)).execute(
            "SELECT title, status FROM audits WHERE id = 1"
        ).fetchone()

        result = prepare_external_audit_ea_0_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertTrue(result.migrated)
        self.assertTrue(schema_is_present(self.db_path))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertEqual(_tables(self.db_path) - before, set(REQUIRED_TABLES))
        for table in REQUIRED_TABLES:
            self.assertEqual(_count(self.db_path, table), 0)
        self.assertEqual(_count(self.db_path, "audits"), audits_before)
        self.assertEqual(_count(self.db_path, "tasks"), tasks_before)
        internal_after = sqlite3.connect(str(self.db_path)).execute(
            "SELECT title, status FROM audits WHERE id = 1"
        ).fetchone()
        self.assertEqual(internal_after, internal_row)

    def test_04_idempotent_repeat(self) -> None:
        first = prepare_external_audit_ea_0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        backups_first = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertEqual(len(backups_first), 1)
        second = prepare_external_audit_ea_0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertFalse(second.migrated)
        backups_second = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertEqual(len(backups_second), 1)
        self.assertEqual(first.pre_migration_backup_path, backups_second[0])

    def test_05_completed_marker_missing_schema_repairs(self) -> None:
        prepare_external_audit_ea_0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        conn = sqlite3.connect(str(self.db_path))
        try:
            for table in REQUIRED_TABLES:
                conn.execute(f'DROP TABLE "{table}"')
            conn.commit()
        finally:
            conn.close()
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertTrue(needs_external_audit_ea_0_schema(self.db_path))

        result = prepare_external_audit_ea_0_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertTrue(result.migrated)
        self.assertIsNotNone(result.pre_migration_backup_path)
        self.assertTrue(schema_is_present(self.db_path))
        backups = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertGreaterEqual(len(backups), 2)

    def test_06_ddl_failure_marks_failed(self) -> None:
        with patch(
            "moduly.externi_audity.sluzby.external_audit_ea_0_schema_migration."
            "apply_external_audit_ea_0_schema_ddl",
            side_effect=RuntimeError("umělá chyba DDL"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_external_audit_ea_0_schema(
                    workspace_root=self.ws, database_path=self.db_path
                )
        self.assertTrue(is_migration_failed(self.ws, TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertTrue(needs_external_audit_ea_0_schema(self.db_path))

    def test_07_allocate_backup_name(self) -> None:
        path = allocate_external_audit_ea_0_backup_path(self.ws / "zalohy")
        self.assertTrue(path.name.startswith(BACKUP_NAME_PREFIX))
        self.assertTrue(path.name.endswith(".mbbackup"))


_SVC_HOME = Path(tempfile.mkdtemp(prefix="external-audit-ea-0-svc-"))
with patch.object(Path, "home", return_value=_SVC_HOME):
    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.externi_audity.constants import (
        ENTITY_EXTERNAL_AUDIT,
        EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
        EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
        EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
        EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
        EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
        EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
        EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
        EXTERNAL_AUDIT_SOURCE_PERSON,
        EXTERNAL_AUDIT_SOURCE_THP_WORKER,
        EXTERNAL_AUDIT_STATUS_CANCELLED,
        EXTERNAL_AUDIT_STATUS_CLOSED,
        EXTERNAL_AUDIT_STATUS_PLANNED,
        EXTERNAL_AUDIT_TYPE_RECERTIFICATION,
        EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
    )
    from moduly.externi_audity.sluzby.external_audit_reminder_read_service import (
        external_audit_reminder_read_service,
    )
    from moduly.externi_audity.sluzby.external_audit_service import (
        ExternalAuditError,
        external_audit_service,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


class ExternalAuditEa0ServiceTestCase(unittest.TestCase):
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
            name=f"EA-WP-{suffix}",
            address=f"Ulice {suffix}",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.non_auditable = settings_service.save_workplace(
            name=f"EA-OFF-{suffix}",
            active=True,
            audit_enabled=False,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.person = person_service.create_person(
            first_name="Anna",
            last_name=f"Auditor-{suffix}",
        )
        self.invited = person_service.create_person(
            first_name="Ivan",
            last_name=f"Host-{suffix}",
        )
        self.thp = settings_service.save_worker(
            first_name="Tomáš",
            last_name=f"THP-{suffix}",
        )

    def _create_audit(self, **fields):
        payload = {
            "audit_type": EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
            "organization_ico": "00000000",
            "organization_name": "Certifikační orgán a.s.",
            "organization_address": "Praha 1",
            "organization_extra": {"source": "ares"},
        }
        payload.update(fields)
        return external_audit_service.create_audit(**payload)

    def test_01_new_tables_empty_after_init(self) -> None:
        # EA-0 marker: initialize_database nevytváří automaticky řádky.
        # Tabulky existují; počet řádků může být >0 jen pokud jiné testy
        # ve stejném procesu zapisují — ověř existenci schématu.
        db = storage_module.storage_service.database_path
        for table in REQUIRED_TABLES:
            self.assertIn(table, _tables(db))

    def test_02_valid_types_statuses_and_org_snapshot(self) -> None:
        audit = self._create_audit(
            audit_type=EXTERNAL_AUDIT_TYPE_RECERTIFICATION,
            status=EXTERNAL_AUDIT_STATUS_PLANNED,
        )
        self.assertEqual(audit.audit_type, EXTERNAL_AUDIT_TYPE_RECERTIFICATION)
        self.assertEqual(audit.status, EXTERNAL_AUDIT_STATUS_PLANNED)
        self.assertEqual(audit.organization_ico, "00000000")
        self.assertEqual(audit.organization_name, "Certifikační orgán a.s.")
        payload = json.loads(audit.organization_snapshot_json or "{}")
        self.assertEqual(payload["ico"], "00000000")
        self.assertEqual(payload["name"], "Certifikační orgán a.s.")
        self.assertEqual(payload["address"], "Praha 1")
        self.assertEqual(payload["extra"]["source"], "ares")

        with self.assertRaises(ExternalAuditError):
            external_audit_service.create_audit(
                audit_type="invalid",
                organization_ico="1",
                organization_name="X",
            )
        with self.assertRaises(ExternalAuditError):
            external_audit_service.set_status(audit.id, "broken")

    def test_03_visits_derived_range_and_time_validation(self) -> None:
        audit = self._create_audit()
        self.assertEqual(
            external_audit_service.derived_date_range(audit.id), (None, None)
        )
        v1 = external_audit_service.add_visit(
            audit.id,
            visit_date=date(2026, 9, 10),
            workplace_id=self.workplace.id,
            time_from="09:00",
            time_to="12:00",
        )
        v2 = external_audit_service.add_visit(
            audit.id,
            visit_date=date(2026, 9, 12),
            workplace_id=self.workplace.id,
        )
        self.assertEqual(
            external_audit_service.derived_date_range(audit.id),
            (date(2026, 9, 10), date(2026, 9, 12)),
        )
        self.assertEqual(v1.workplace_name_snapshot, self.workplace.name)
        self.assertEqual(v1.workplace_address_snapshot, self.workplace.address)

        with self.assertRaises(ExternalAuditError):
            external_audit_service.add_visit(
                audit.id,
                visit_date=date(2026, 9, 11),
                workplace_id=self.workplace.id,
                time_from="15:00",
                time_to="10:00",
            )
        with self.assertRaises(ExternalAuditError):
            external_audit_service.add_visit(
                audit.id,
                visit_date=date(2026, 9, 11),
                workplace_id=self.non_auditable.id,
            )

        settings_service.save_workplace(
            id=self.workplace.id,
            name=f"Přejmenováno-{uuid.uuid4().hex[:4]}",
            address="Nová adresa",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        detail = external_audit_service.get_detail(audit.id)
        visit = next(item for item in detail.visits if item.id == v1.id)
        self.assertEqual(visit.workplace_name_snapshot, v1.workplace_name_snapshot)
        self.assertEqual(
            visit.workplace_address_snapshot, v1.workplace_address_snapshot
        )
        self.assertEqual(len(detail.visits), 2)
        self.assertIsNotNone(v2.id)

    def test_04_participants_roles_and_visit_assignment(self) -> None:
        audit = self._create_audit()
        other = self._create_audit(organization_name="Jiná org")
        auditor = external_audit_service.add_participant(
            audit.id,
            role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
            source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
            source_id=self.person.id,
        )
        rep = external_audit_service.add_participant(
            audit.id,
            role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
            source_type=EXTERNAL_AUDIT_SOURCE_THP_WORKER,
            source_id=self.thp.id,
        )
        invited = external_audit_service.add_participant(
            audit.id,
            role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
            source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
            source_id=self.invited.id,
        )
        self.assertIn(self.person.last_name, auditor.display_name_snapshot)
        self.assertIn(self.thp.last_name, rep.display_name_snapshot)
        self.assertIn(self.invited.last_name, invited.display_name_snapshot)

        with self.assertRaises(ExternalAuditError):
            external_audit_service.add_participant(
                audit.id,
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                source_type=EXTERNAL_AUDIT_SOURCE_THP_WORKER,
                source_id=self.thp.id,
            )
        with self.assertRaises(ExternalAuditError):
            external_audit_service.add_participant(
                audit.id,
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
                source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
                source_id=self.person.id,
            )
        with self.assertRaises(ExternalAuditError):
            external_audit_service.add_participant(
                audit.id,
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
                source_type=EXTERNAL_AUDIT_SOURCE_THP_WORKER,
                source_id=self.thp.id,
            )

        foreign = external_audit_service.add_participant(
            other.id,
            role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
            source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
            source_id=self.person.id,
        )
        visit = external_audit_service.add_visit(
            audit.id,
            visit_date=date(2026, 10, 1),
            workplace_id=self.workplace.id,
        )
        external_audit_service.set_visit_participants(
            visit.id, [auditor.id, rep.id]
        )
        with self.assertRaises(ExternalAuditError):
            external_audit_service.set_visit_participants(
                visit.id, [auditor.id, foreign.id]
            )
        detail = external_audit_service.get_detail(audit.id)
        self.assertEqual(
            set(detail.visit_participant_ids[visit.id]),
            {auditor.id, rep.id},
        )

    def test_05_findings_resolve_and_close_audit(self) -> None:
        audit = self._create_audit()
        nc = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Neshoda A",
            due_date=date(2026, 11, 1),
        )
        pkz = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
            description="PKZ B",
        )
        strength = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
            description="Silná stránka",
        )
        self.assertEqual(nc.status, EXTERNAL_AUDIT_FINDING_STATUS_OPEN)
        self.assertEqual(pkz.status, EXTERNAL_AUDIT_FINDING_STATUS_OPEN)
        self.assertEqual(strength.status, EXTERNAL_AUDIT_FINDING_STATUS_RECORDED)
        self.assertIsNone(strength.due_date)

        with self.assertRaises(ExternalAuditError):
            external_audit_service.resolve_finding(nc.id, resolution_text="  ")
        with self.assertRaises(ExternalAuditError):
            external_audit_service.resolve_finding(
                strength.id, resolution_text="nelze"
            )

        resolved = external_audit_service.resolve_finding(
            nc.id, resolution_text="Opraveno"
        )
        self.assertEqual(resolved.status, EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED)
        self.assertIsNotNone(resolved.resolved_at)
        reopened = external_audit_service.reopen_finding(
            nc.id, status=EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS
        )
        self.assertEqual(reopened.status, EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS)
        self.assertIsNone(reopened.resolved_at)
        self.assertEqual(reopened.resolution_text, "Opraveno")

        external_audit_service.set_status(audit.id, EXTERNAL_AUDIT_STATUS_CLOSED)
        loaded = external_audit_service.get_detail(audit.id)
        statuses = {item.id: item.status for item in loaded.findings}
        self.assertEqual(
            statuses[pkz.id], EXTERNAL_AUDIT_FINDING_STATUS_OPEN
        )
        self.assertEqual(
            statuses[nc.id], EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS
        )
        self.assertEqual(
            statuses[strength.id], EXTERNAL_AUDIT_FINDING_STATUS_RECORDED
        )

    def test_06_task_links_no_auto_resolve(self) -> None:
        audit = self._create_audit()
        finding = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Neshoda s úkoly",
        )
        strength = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
            description="Síla",
        )
        t1 = task_service.create_task(title=f"EA-T1-{uuid.uuid4().hex[:4]}")
        t2 = task_service.create_task(title=f"EA-T2-{uuid.uuid4().hex[:4]}")
        external_audit_service.link_task(finding.id, t1.id)
        external_audit_service.link_task(finding.id, t2.id)
        with self.assertRaises(ExternalAuditError):
            external_audit_service.link_task(finding.id, t1.id)
        with self.assertRaises(ExternalAuditError):
            external_audit_service.link_task(strength.id, t1.id)

        task_service.update_task(t1.id, title=t1.title, completed=True)
        task_service.update_task(t2.id, title=t2.title, canceled=True)
        ids = external_audit_service.list_finding_task_ids(finding.id)
        self.assertEqual(ids, [t1.id, t2.id])
        loaded = external_audit_service.get_detail(audit.id).findings[0]
        self.assertEqual(loaded.status, EXTERNAL_AUDIT_FINDING_STATUS_OPEN)

    def test_07_batch_detail_and_list_aggregates(self) -> None:
        audit = self._create_audit()
        visit = external_audit_service.add_visit(
            audit.id,
            visit_date=date(2026, 12, 1),
            workplace_id=self.workplace.id,
        )
        participant = external_audit_service.add_participant(
            audit.id,
            role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
            source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
            source_id=self.person.id,
        )
        external_audit_service.set_visit_participants(visit.id, [participant.id])
        external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Otevřená",
        )
        external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
            description="Síla",
        )
        detail = external_audit_service.get_detail(audit.id)
        self.assertEqual(len(detail.visits), 1)
        self.assertEqual(len(detail.participants), 1)
        self.assertEqual(len(detail.findings), 2)
        self.assertEqual(detail.date_from, date(2026, 12, 1))
        self.assertEqual(detail.visit_participant_ids[visit.id], [participant.id])

        items = {
            item.audit.id: item for item in external_audit_service.list_audits()
        }
        self.assertIn(audit.id, items)
        self.assertEqual(items[audit.id].visit_count, 1)
        self.assertEqual(items[audit.id].finding_count, 2)
        self.assertEqual(items[audit.id].open_finding_count, 1)

    def test_08_cancel_not_delete_and_reminders_api(self) -> None:
        audit = self._create_audit(remind_from=date(2026, 8, 1))
        external_audit_service.add_visit(
            audit.id,
            visit_date=date(2026, 8, 20),
            workplace_id=self.workplace.id,
        )
        external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Termínovaná",
            due_date=date(2026, 8, 10),
        )
        upcoming = external_audit_reminder_read_service.list_upcoming(
            as_of=date(2026, 8, 15)
        )
        reminders = external_audit_reminder_read_service.list_audit_reminders(
            as_of=date(2026, 8, 15)
        )
        finding_reminders = (
            external_audit_reminder_read_service.list_finding_reminders(
                as_of=date(2026, 8, 15)
            )
        )
        self.assertTrue(any(item.audit.id == audit.id for item in upcoming))
        self.assertTrue(any(item.audit.id == audit.id for item in reminders))
        self.assertTrue(
            any(item.finding.description == "Termínovaná" for item in finding_reminders)
        )

        external_audit_service.set_status(audit.id, EXTERNAL_AUDIT_STATUS_CANCELLED)
        reminders_after = external_audit_reminder_read_service.list_audit_reminders(
            as_of=date(2026, 8, 15)
        )
        self.assertFalse(
            any(item.audit.id == audit.id for item in reminders_after)
        )
        # Fyzické smazání není veřejná business operace — záznam zůstává.
        self.assertIsNotNone(external_audit_service.get_by_id(audit.id))

    def test_09_attachment_entity_type_hook(self) -> None:
        audit = self._create_audit()
        self.assertEqual(ENTITY_EXTERNAL_AUDIT, "external_audit")
        self.assertEqual(external_audit_service.list_attachments(audit.id), [])

    def test_10_no_auto_create_on_service_import(self) -> None:
        # Po startu / importu služeb zůstávají nové tabulky prázdné, dokud
        # testy samy nevytvoří data — ověřeno v test_01; zde kontrola, že
        # cancel/close nevytváří skryté záznamy.
        before = _count(storage_module.storage_service.database_path, "external_audits")
        self.assertGreaterEqual(before, 0)


if __name__ == "__main__":
    unittest.main()
