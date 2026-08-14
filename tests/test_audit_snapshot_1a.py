"""AUDIT-SNAPSHOT-1a: atomický backfill + oprava kontroly schématu."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="audit-snapshot-1a-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_HOME)
_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)
session_module.reconfigure_database_engine(force=True)

from core.database.database_initializer import initialize_database  # noqa: E402

initialize_database()

from core.database.upgrade_guard import (  # noqa: E402
    PreMigrationBackupError,
    clear_transition_complete,
    is_transition_complete,
    mark_migration_complete,
    read_migration_state,
    write_migration_state,
)
from core.shared.constants import (  # noqa: E402
    CONTROL_RESULT_VYHOVUJE,
    ENTITY_AUDITY,
)
from core.shared.sluzby.control_result_service import (  # noqa: E402
    ControlPointContext,
    control_result_service,
)
from core.shared.sluzby.finding_service import finding_service  # noqa: E402
from moduly.audity.constants import (  # noqa: E402
    AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    AUDIT_QUESTION_KIND_LEGACY,
)
from moduly.audity.modely.audit import Audit  # noqa: E402
from moduly.audity.modely.audit_question_snapshot import (  # noqa: E402
    AuditQuestionSnapshot,
)
from moduly.audity.repository.audit_program_repository import (  # noqa: E402
    AuditProgramRepository,
)
from moduly.audity.sluzby.audit_knowledge_service import (  # noqa: E402
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_program_service import (  # noqa: E402
    audit_program_service,
)
from moduly.audity.sluzby.audit_question_snapshot_service import (  # noqa: E402
    audit_question_snapshot_service,
    snapshot_key,
)
from moduly.audity.sluzby.audit_service import audit_service  # noqa: E402
from moduly.audity.sluzby.audit_snapshot_backfill_service import (  # noqa: E402
    TRANSITION_ID as BACKFILL_TRANSITION,
    AuditSnapshotBackfillError,
    prepare_audit_snapshot_backfill,
)
from moduly.audity.sluzby.audit_snapshot_schema_migration import (  # noqa: E402
    TRANSITION_ID as SCHEMA_TRANSITION,
    apply_audit_snapshot_schema_ddl,
    needs_audit_snapshot_schema,
    prepare_audit_snapshot_schema,
    schema_is_present,
)
from moduly.audity.sluzby.audit_verification_service import (  # noqa: E402
    audit_verification_service,
)
from sqlalchemy import select  # noqa: E402

from core.database.session import get_session  # noqa: E402

_WS = storage_module.storage_service.base
_DB = storage_module.storage_service.database_path


def _count(table: str) -> int:
    conn = sqlite3.connect(str(_DB))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _clear_backfill_state() -> None:
    state = read_migration_state(_WS)
    completed = [
        item
        for item in (state.get("completed_transitions") or [])
        if item != BACKFILL_TRANSITION
    ]
    state["completed_transitions"] = completed
    state["in_progress"] = None
    if (state.get("last_completed") or {}).get("transition_id") == BACKFILL_TRANSITION:
        state["last_completed"] = None
    if (state.get("last_failed") or {}).get("transition_id") == BACKFILL_TRANSITION:
        state["last_failed"] = None
    write_migration_state(_WS, state)
    for backup in (_WS / "zalohy").glob("pre_audit_snapshot_backfill_*"):
        backup.unlink()


def _delete_all_snapshots_and_reset_audits() -> None:
    with get_session() as session:
        for row in list(session.scalars(select(AuditQuestionSnapshot))):
            session.delete(row)
        for audit in list(session.scalars(select(Audit))):
            audit.methodology_source = None
            audit.questions_frozen_at = None
            audit.methodology_generation = None
        session.commit()

class AuditSnapshot1aBackfillTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._home = patch.object(Path, "home", return_value=_HOME)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        initialize_database()
        prepare_audit_snapshot_schema(
            workspace_root=storage_module.storage_service.base,
            database_path=storage_module.storage_service.database_path,
        )
        cls.processes = [
            p
            for p in audit_knowledge_service.get_processes(ensure=True)
            if p.has_knowledge_file
        ]
        if len(cls.processes) < 2:
            raise AssertionError("Očekávány alespoň 2 procesy s knowledge souborem")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self._home_ctx = patch.object(Path, "home", return_value=_HOME)
        self._home_ctx.start()
        importlib.reload(storage_module)
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        global _WS, _DB
        _WS = storage_module.storage_service.base
        _DB = storage_module.storage_service.database_path
        _clear_backfill_state()
        _delete_all_snapshots_and_reset_audits()
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)

    def tearDown(self) -> None:
        self._home_ctx.stop()
    def _first_assertion(self, process_id: str):
        tree = audit_knowledge_service.get_knowledge_tree(ensure=False)
        for root in tree:
            if root.process_id != process_id:
                continue
            for node in root.children:
                section = node.section or {}
                questions = audit_knowledge_service.get_audit_questions(section)
                if questions:
                    q = questions[0]
                    return (
                        process_id,
                        root.label,
                        str(section.get("id") or node.node_id),
                        str(section.get("nazev") or node.label),
                        str(q.get("id")),
                        str(q.get("text") or q.get("nazev")),
                    )
        self.fail(f"Žádné tvrzení v procesu {process_id}")

    def test_existing_audit_gets_full_snapshot(self) -> None:
        process = self.processes[0]
        audit = audit_service.create_audit(title="Full snapshot")
        result = prepare_audit_snapshot_backfill(
            workspace_root=_WS, database_path=_DB
        )
        self.assertTrue(result.migrated)
        self.assertEqual(result.processed_audits, 1)

        reloaded = audit_service.get_by_id(audit.id)
        self.assertEqual(reloaded.methodology_source, AUDIT_METHODOLOGY_SOURCE_SNAPSHOT)
        self.assertEqual(
            reloaded.methodology_generation, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
        )
        self.assertIsNotNone(reloaded.questions_frozen_at)

        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertGreater(len(snaps), 0)
        methodology = audit_question_snapshot_service.build_snapshot_for_audit(
            audit.id, ensure=False
        )
        self.assertGreaterEqual(len(snaps), len(methodology))
        self.assertTrue(all(s.question_kind == AUDIT_QUESTION_KIND_LEGACY for s in snaps))

    def test_audit_without_results_includes_unevaluated_questions(self) -> None:
        audit = audit_service.create_audit(title="Bez výsledků")
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        methodology = audit_question_snapshot_service.build_snapshot_for_audit(
            audit.id, ensure=False
        )
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual(len(snaps), len(methodology))
        self.assertEqual(_count("control_results"), 0)

    def test_evaluated_question_uses_control_result_text(self) -> None:
        process = self.processes[0]
        (
            area_id,
            area_label,
            section_id,
            section_label,
            cp_id,
            _current_text,
        ) = self._first_assertion(process.id)
        historical_text = "HISTORICKÝ TEXT OTÁZKY ZE SPISU"
        audit = audit_service.create_audit(title="Historický text")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=area_id,
                area_label=area_label,
                section_id=section_id,
                section_label=section_label,
                control_point_id=cp_id,
                control_point_label=historical_text,
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        with get_session() as session:
            snap = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id == cp_id,
                    AuditQuestionSnapshot.process_id == area_id,
                    AuditQuestionSnapshot.section_id == section_id,
                )
            )
        self.assertIsNotNone(snap)
        self.assertEqual(snap.assertion_text, historical_text)

    def test_orphan_result_outside_json_stays_in_snapshot(self) -> None:
        audit = audit_service.create_audit(title="Orphan JSON")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="ghost_process",
                area_label="Duch procesu",
                section_id="ghost_section",
                section_label="Duch sekce",
                control_point_id="ghost_q",
                control_point_label="Orphan tvrzení mimo JSON",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id,
                        AuditQuestionSnapshot.assertion_id == "ghost_q",
                    )
                )
            )
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].assertion_text, "Orphan tvrzení mimo JSON")
        self.assertEqual(snaps[0].process_id, "ghost_process")

    def test_result_outside_planned_processes_stays(self) -> None:
        first, second = self.processes[0], self.processes[1]
        (
            area_id,
            area_label,
            section_id,
            section_label,
            cp_id,
            text,
        ) = self._first_assertion(second.id)

        program = audit_program_service.create_program(name="Prog snapshot")
        visit = audit_program_service.add_visit(
            program.id,
            planned_year=2026,
            planned_month=3,
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id=first.id,
            process_name=first.nazev,
        )

        audit = audit_service.create_audit(
            title="Mimo planned",
            program_id=program.id,
            program_visit_id=visit.id,
        )
        visit.audit_id = audit.id
        AuditProgramRepository().update_visit(visit)

        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=area_id,
                area_label=area_label,
                section_id=section_id,
                section_label=section_label,
                control_point_id=cp_id,
                control_point_label=text,
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )

        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        with get_session() as session:
            snap = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id == cp_id,
                    AuditQuestionSnapshot.process_id == area_id,
                )
            )
        self.assertIsNotNone(snap)
        self.assertEqual(snap.assertion_text, text)

    def test_all_control_results_have_snapshot_counterpart(self) -> None:
        process = self.processes[0]
        info = self._first_assertion(process.id)
        audit = audit_service.create_audit(title="CR coverage")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=info[0],
                area_label=info[1],
                section_id=info[2],
                section_label=info[3],
                control_point_id=info[4],
                control_point_label=info[5],
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="orphan_p",
                area_label="O",
                section_id="orphan_s",
                section_label="S",
                control_point_id="orphan_a",
                control_point_label="Orphan",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        results = control_result_service.get_for_entity(ENTITY_AUDITY, audit.id)
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        from moduly.audity.sluzby.audit_snapshot_backfill_service import (
            _match_result_to_drafts,
        )
        from moduly.audity.sluzby.audit_question_snapshot_service import (
            AuditQuestionSnapshotDraft,
        )

        drafts = [
            AuditQuestionSnapshotDraft(
                audit_id=audit.id,
                process_id=s.process_id,
                process_name=s.process_name,
                section_id=s.section_id,
                section_name=s.section_name,
                assertion_id=s.assertion_id,
                assertion_text=s.assertion_text,
                verification_type=s.verification_type,
                severity=s.severity,
                question_kind=s.question_kind,
                display_order=s.display_order,
            )
            for s in snaps
        ]
        for row in results:
            self.assertIsNotNone(_match_result_to_drafts(row, drafts))

    def test_visit_without_audit_id_is_not_snapshotted(self) -> None:
        program = audit_program_service.create_program(name="Bez auditu")
        repo = AuditProgramRepository()
        from moduly.audity.modely.audit_program import AuditProgramVisit

        visit = repo.add_visit(
            AuditProgramVisit(
                program_id=program.id,
                planned_year=2026,
                planned_month=1,
                status="planned",
            )
        )
        self.assertIsNone(visit.audit_id)
        before = _count("audit_question_snapshots")
        result = prepare_audit_snapshot_backfill(
            workspace_root=_WS, database_path=_DB
        )
        self.assertEqual(result.visits_without_audit, 1)
        self.assertEqual(_count("audit_question_snapshots"), before)

    def test_multiple_audits_atomic_and_idempotent(self) -> None:
        a1 = audit_service.create_audit(title="A1")
        a2 = audit_service.create_audit(title="A2")
        finding_service.create(
            entity_type=ENTITY_AUDITY, entity_id=a1.id, description="F1"
        )
        counts_before = {
            "audits": _count("audits"),
            "findings": _count("findings"),
            "control_results": _count("control_results"),
            "tasks": _count("tasks"),
            "audit_programs": _count("audit_programs"),
        }
        first = prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertEqual(first.processed_audits, 2)
        snaps_after_first = _count("audit_question_snapshots")
        self.assertGreater(snaps_after_first, 0)

        second = prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertFalse(second.migrated)
        self.assertEqual(second.skipped_audits, 2)
        self.assertEqual(_count("audit_question_snapshots"), snaps_after_first)
        for key, value in counts_before.items():
            self.assertEqual(_count(key), value)

    def test_failure_rolls_back_entire_backfill(self) -> None:
        audit_service.create_audit(title="Fail1")
        audit_service.create_audit(title="Fail2")
        call = {"n": 0}

        def validate_fail(audit, **kwargs):
            call["n"] += 1
            # 1–2 = před zápisem, 3+ = po zápisu uvnitř transakce
            if call["n"] >= 3:
                raise AuditSnapshotBackfillError(f"umělá chyba auditu {audit.id}")

        with patch(
            "moduly.audity.sluzby.audit_snapshot_backfill_service._validate_audit_snapshot",
            side_effect=validate_fail,
        ):
            with self.assertRaises(AuditSnapshotBackfillError):
                prepare_audit_snapshot_backfill(
                    workspace_root=_WS, database_path=_DB
                )

        self.assertEqual(_count("audit_question_snapshots"), 0)
        for audit in audit_service.get_all():
            self.assertIsNone(audit.methodology_source)
            self.assertIsNone(audit.questions_frozen_at)
        self.assertFalse(is_transition_complete(_WS, BACKFILL_TRANSITION))
        backups = list((_WS / "zalohy").glob("pre_audit_snapshot_backfill_*"))
        self.assertEqual(len(backups), 1)

    def test_backup_failure_blocks_backfill(self) -> None:
        audit_service.create_audit(title="No backup")
        with patch(
            "moduly.audity.sluzby.audit_snapshot_backfill_service.create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_audit_snapshot_backfill(
                    workspace_root=_WS, database_path=_DB
                )
        self.assertEqual(_count("audit_question_snapshots"), 0)
        self.assertFalse(is_transition_complete(_WS, BACKFILL_TRANSITION))

    def test_ensure_catalogs_once_for_all_audits(self) -> None:
        audit_service.create_audit(title="E1")
        audit_service.create_audit(title="E2")
        audit_service.create_audit(title="E3")
        ensure_calls = {"count": 0}
        original = audit_knowledge_service.ensure_catalogs

        def counting():
            ensure_calls["count"] += 1
            return original()

        with patch.object(
            audit_knowledge_service, "ensure_catalogs", side_effect=counting
        ):
            prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertEqual(ensure_calls["count"], 1)

    def test_original_data_unchanged(self) -> None:
        process = self.processes[0]
        info = self._first_assertion(process.id)
        audit = audit_service.create_audit(title="Data intact")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=info[0],
                area_label=info[1],
                section_id=info[2],
                section_label=info[3],
                control_point_id=info[4],
                control_point_label=info[5],
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="poznámka",
            photo_path="photos/test.jpg",
        )
        finding_service.create(
            entity_type=ENTITY_AUDITY, entity_id=audit.id, description="Z"
        )
        audit_verification_service.set_override(
            audit.id,
            area_id=info[0],
            section_id=info[2],
            control_point_id=info[4],
            verification_type="teren",
        )
        cr_before = control_result_service.get_for_entity(ENTITY_AUDITY, audit.id)[0]
        overrides_before = audit_verification_service.overrides_map(audit.id)

        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)

        cr_after = control_result_service.get_for_entity(ENTITY_AUDITY, audit.id)[0]
        self.assertEqual(cr_after.result, cr_before.result)
        self.assertEqual(cr_after.note, cr_before.note)
        self.assertEqual(cr_after.photo_path, cr_before.photo_path)
        self.assertEqual(cr_after.source_control_point_label, info[5])
        self.assertEqual(
            audit_verification_service.overrides_map(audit.id), overrides_before
        )
        self.assertEqual(len(finding_service.get_for_entity(ENTITY_AUDITY, audit.id)), 1)


class AuditSnapshotSchemaCompletedMismatchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._home_ctx = patch.object(Path, "home", return_value=_HOME)
        self._home_ctx.start()
        importlib.reload(storage_module)
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        global _WS, _DB
        _WS = storage_module.storage_service.base
        _DB = storage_module.storage_service.database_path
        prepare_audit_snapshot_schema(workspace_root=_WS, database_path=_DB)

    def tearDown(self) -> None:
        self._home_ctx.stop()

    def test_completed_state_with_restored_old_db_repairs_schema(self) -> None:
        # Simulace: marker completed, ale schema chybí (obnova starší DB).
        mark_migration_complete(
            _WS, backup_path=None, transition_id=SCHEMA_TRANSITION
        )
        self.assertTrue(is_transition_complete(_WS, SCHEMA_TRANSITION))

        # Odstraň snapshot tabulku a sloupce = „starší DB“.
        conn = sqlite3.connect(str(_DB))
        try:
            conn.execute("DROP TABLE IF EXISTS audit_question_snapshots")
            # SQLite neumí DROP COLUMN spolehlivě ve všech verzích — vytvoříme
            # legacy audits bez snapshot sloupců přes rebuild.
            cols = {
                row[1] for row in conn.execute("PRAGMA table_info(audits)").fetchall()
            }
            if "methodology_source" in cols:
                conn.execute("ALTER TABLE audits RENAME TO audits_legacy_full")
                conn.execute(
                    """
                    CREATE TABLE audits (
                        id INTEGER PRIMARY KEY,
                        number VARCHAR(30) DEFAULT '',
                        year INTEGER,
                        planned_month INTEGER,
                        audit_date DATE,
                        started_at DATE,
                        finished_at DATE,
                        status VARCHAR(30) DEFAULT 'Plánováno' NOT NULL,
                        audit_type VARCHAR(30) DEFAULT 'Řádný' NOT NULL,
                        workplace_id INTEGER,
                        workplace_name VARCHAR(150) DEFAULT '',
                        title VARCHAR(250) DEFAULT '',
                        program_id INTEGER,
                        program_visit_id INTEGER,
                        silne_stranky TEXT DEFAULT '' NOT NULL,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO audits (
                        id, number, year, planned_month, audit_date, started_at,
                        finished_at, status, audit_type, workplace_id, workplace_name,
                        title, program_id, program_visit_id, silne_stranky,
                        created_at, updated_at
                    )
                    SELECT
                        id, number, year, planned_month, audit_date, started_at,
                        finished_at, status, audit_type, workplace_id, workplace_name,
                        title, program_id, program_visit_id, silne_stranky,
                        created_at, updated_at
                    FROM audits_legacy_full
                    """
                )
                conn.execute("DROP TABLE audits_legacy_full")
            conn.commit()
        finally:
            conn.close()

        self.assertTrue(needs_audit_snapshot_schema(_DB))
        self.assertTrue(is_transition_complete(_WS, SCHEMA_TRANSITION))

        result = prepare_audit_snapshot_schema(
            workspace_root=_WS, database_path=_DB
        )
        self.assertTrue(result.migrated)
        self.assertTrue(schema_is_present(_DB))
        self.assertTrue(is_transition_complete(_WS, SCHEMA_TRANSITION))
        self.assertIsNotNone(result.pre_migration_backup_path)
        self.assertTrue(result.pre_migration_backup_path.is_file())


if __name__ == "__main__":
    unittest.main()
