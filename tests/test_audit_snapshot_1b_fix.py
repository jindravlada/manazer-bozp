"""AUDIT-SNAPSHOT-1b-fix: is_in_scope — orphan zachován, nezobrazen."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="audit-snapshot-1b-fix-"))
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
    is_transition_complete,
    mark_migration_complete,
    read_migration_state,
    write_migration_state,
)
from core.shared.constants import (  # noqa: E402
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE,
    ENTITY_AUDITY,
)
from core.shared.sluzby.control_result_service import (  # noqa: E402
    ControlPointContext,
    control_result_service,
)
from core.shared.verification_type import (  # noqa: E402
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
)
from moduly.audity.constants import (  # noqa: E402
    AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    AUDIT_QUESTION_KIND_LEGACY,
)
from moduly.audity.modely.audit import Audit  # noqa: E402
from moduly.audity.modely.audit_question_snapshot import (  # noqa: E402
    AuditQuestionSnapshot,
)
from moduly.audity.sluzby.audit_annual_export_context_service import (  # noqa: E402
    audit_annual_export_context_service,
)
from moduly.audity.sluzby.audit_export_context_service import (  # noqa: E402
    DETAILED_REPORT_DOCUMENT_CONFIG,
    PROTOCOL_DOCUMENT_CONFIG,
    AuditExportContext,
)
from moduly.audity.sluzby.audit_knowledge_service import (  # noqa: E402
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_question_source_service import (  # noqa: E402
    audit_question_source_service,
)
from moduly.audity.sluzby.audit_service import audit_service  # noqa: E402
from moduly.audity.sluzby.audit_snapshot_backfill_service import (  # noqa: E402
    prepare_audit_snapshot_backfill,
)
from moduly.audity.sluzby.audit_snapshot_schema_migration import (  # noqa: E402
    prepare_audit_snapshot_schema,
)
from moduly.audity.sluzby.audit_snapshot_scope_migration import (  # noqa: E402
    TRANSITION_ID as SCOPE_TRANSITION,
    AuditSnapshotScopeFixError,
    ensure_scope_column,
    prepare_audit_snapshot_scope_fix,
    scope_column_present,
)
from moduly.audity.sluzby.audit_terrain_checklist_service import (  # noqa: E402
    audit_terrain_checklist_service,
)
from moduly.audity.sluzby.audit_verification_service import (  # noqa: E402
    audit_verification_service,
)
from sqlalchemy import select  # noqa: E402

from core.database.session import get_session  # noqa: E402

_WS = storage_module.storage_service.base
_DB = storage_module.storage_service.database_path


def _cr_fingerprint(audit_id: int) -> list[tuple]:
    conn = sqlite3.connect(str(_DB))
    try:
        return list(
            conn.execute(
                "SELECT id, result, note, photo_path, source_control_point_id, "
                "source_control_point_label FROM control_results "
                "WHERE entity_type=? AND entity_id=? ORDER BY id",
                (ENTITY_AUDITY, audit_id),
            ).fetchall()
        )
    finally:
        conn.close()


class AuditSnapshot1bFixTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
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
        ensure_scope_column(storage_module.storage_service.database_path)
        cls.processes = [
            p
            for p in audit_knowledge_service.get_processes(ensure=True)
            if p.has_knowledge_file
        ]
        if not cls.processes:
            raise AssertionError("Očekáván alespoň 1 proces s knowledge souborem")

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
        with get_session() as session:
            for row in list(session.scalars(select(AuditQuestionSnapshot))):
                session.delete(row)
            for audit in list(session.scalars(select(Audit))):
                session.delete(audit)
            session.commit()
        conn = sqlite3.connect(str(_DB))
        try:
            conn.execute(
                "DELETE FROM control_results WHERE entity_type = ?", (ENTITY_AUDITY,)
            )
            conn.execute("DELETE FROM audit_verification_overrides")
            conn.commit()
        finally:
            conn.close()
        state = read_migration_state(_WS)
        completed = [
            item
            for item in (state.get("completed_transitions") or [])
            if item != SCOPE_TRANSITION
        ]
        state["completed_transitions"] = completed
        state["in_progress"] = None
        write_migration_state(_WS, state)
        for backup in (_WS / "zalohy").glob("pre_audit_snapshot_scope_fix_*"):
            backup.unlink()

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

    def _seed_with_orphan(self):
        info = self._first_assertion(self.processes[0].id)
        audit = audit_service.create_audit(title="Scope")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=info[0],
                area_label=info[1],
                section_id=info[2],
                section_label=info[3],
                control_point_id=info[4],
                control_point_label="IN SCOPE TEXT",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="ghost_p",
                area_label="Ghost",
                section_id="ghost_s",
                section_label="Ghost sec",
                control_point_id="ghost_q",
                control_point_label="ORPHAN ONLY",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        prepare_audit_snapshot_scope_fix(workspace_root=_WS, database_path=_DB)
        return audit_service.get_by_id(audit.id), info

    def test_valid_question_is_in_scope(self) -> None:
        audit, info = self._seed_with_orphan()
        with get_session() as session:
            snap = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id == info[4],
                    AuditQuestionSnapshot.process_id == info[0],
                )
            )
        self.assertIsNotNone(snap)
        self.assertTrue(snap.is_in_scope)

    def test_orphan_is_out_of_scope(self) -> None:
        audit, _info = self._seed_with_orphan()
        with get_session() as session:
            orphan = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id == "ghost_q",
                )
            )
        self.assertIsNotNone(orphan)
        self.assertFalse(orphan.is_in_scope)

    def test_orphan_control_result_unchanged(self) -> None:
        info = self._first_assertion(self.processes[0].id)
        audit = audit_service.create_audit(title="CR")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=info[0],
                area_label=info[1],
                section_id=info[2],
                section_label=info[3],
                control_point_id=info[4],
                control_point_label="ok",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="n1",
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="ghost_p",
                area_label="Ghost",
                section_id="ghost_s",
                section_label="Ghost sec",
                control_point_id="ghost_q",
                control_point_label="ORPHAN ONLY",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
            note="orphan-note",
            photo_path="photos/x.jpg",
        )
        before = _cr_fingerprint(audit.id)
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        prepare_audit_snapshot_scope_fix(workspace_root=_WS, database_path=_DB)
        self.assertEqual(_cr_fingerprint(audit.id), before)

    def test_orphan_snapshot_row_remains(self) -> None:
        audit, _ = self._seed_with_orphan()
        with get_session() as session:
            count = len(
                list(
                    session.scalars(
                        select(AuditQuestionSnapshot).where(
                            AuditQuestionSnapshot.audit_id == audit.id,
                            AuditQuestionSnapshot.assertion_id == "ghost_q",
                        )
                    )
                )
            )
        self.assertEqual(count, 1)

    def test_orphan_hidden_from_source_and_tabs(self) -> None:
        audit, info = self._seed_with_orphan()
        source = audit_question_source_service.resolve_for_audit(audit.id)
        ids = {a.assertion_id for a in source.assertions}
        self.assertIn(info[4], ids)
        self.assertNotIn("ghost_q", ids)
        for vt in (VERIFICATION_TYPE_DOCUMENTATION, VERIFICATION_TYPE_TERRAIN):
            listed = audit_verification_service.list_assertions(
                audit.id, verification_type=vt
            )
            self.assertFalse(any(r.control_point_id == "ghost_q" for r in listed))

    def test_orphan_not_in_protocol_or_detailed(self) -> None:
        audit, _ = self._seed_with_orphan()
        protocol = AuditExportContext(
            audit=audit, config=PROTOCOL_DOCUMENT_CONFIG
        ).summary_appendix_assertions().plain_text()
        detailed = AuditExportContext(
            audit=audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions().plain_text()
        self.assertNotIn("ORPHAN ONLY", protocol)
        self.assertNotIn("ORPHAN ONLY", detailed)
        self.assertIn("IN SCOPE TEXT", protocol)

    def test_orphan_not_in_terrain_checklist(self) -> None:
        audit, info = self._seed_with_orphan()
        with get_session() as session:
            snap = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id == info[4],
                )
            )
            snap.verification_type = VERIFICATION_TYPE_TERRAIN
            session.commit()
        plain = audit_terrain_checklist_service._checklist_content(audit.id).plain_text()
        self.assertNotIn("ORPHAN ONLY", plain)

    def test_orphan_not_in_annual_severity(self) -> None:
        from moduly.audity.sluzby.audit_annual_export_context_service import (
            AuditAnnualMetrics,
        )

        audit, _ = self._seed_with_orphan()
        year = datetime.now().year
        with get_session() as session:
            db = session.get(Audit, audit.id)
            db.year = year
            db.started_at = datetime(year, 1, 15).date()
            db.finished_at = datetime(year, 1, 16).date()
            session.commit()
        audits = [audit_service.get_by_id(audit.id)]
        metrics = AuditAnnualMetrics(
            year=year,
            audits_count=1,
            workplaces_count=1,
            processes_count=1,
            control_points_count=1,
            ratings_vyhovuje=1,
            ratings_vyhovuje_s_doporucenim=0,
            ratings_nevyhovuje=0,
            findings_count=0,
            measures_total=0,
            measures_open=0,
            measures_closed=0,
        )
        severity = audit_annual_export_context_service._compute_severity_assessment(
            audits, metrics, []
        )
        # Orphan NEVYHOVUJE nesmí vstoupit do váhového skóre.
        self.assertEqual(severity.weighted_score, 0)
        self.assertEqual(sum(severity.counts_by_severity.values()), 0)

    def test_valid_question_survives_json_removal(self) -> None:
        audit, info = self._seed_with_orphan()
        with patch.object(audit_knowledge_service, "get_audit_questions", return_value=[]):
            source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertTrue(any(a.assertion_id == info[4] for a in source.assertions))
        appendix = AuditExportContext(
            audit=audit, config=PROTOCOL_DOCUMENT_CONFIG
        ).summary_appendix_assertions().plain_text()
        self.assertIn("IN SCOPE TEXT", appendix)

    def test_reading_does_not_recompute_scope_against_json(self) -> None:
        audit, info = self._seed_with_orphan()
        with get_session() as session:
            snap = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id == info[4],
                )
            )
            snap.is_in_scope = True
            session.commit()
        # I když JSON „říká“ že otázka neexistuje, is_in_scope zůstane True.
        with patch.object(audit_knowledge_service, "get_audit_questions", return_value=[]):
            with patch.object(
                audit_knowledge_service,
                "get_knowledge_tree",
                side_effect=AssertionError("nesmí přepočítávat proti JSON"),
            ):
                source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertTrue(any(a.assertion_id == info[4] for a in source.assertions))

    def test_classification_idempotent_and_complete_check(self) -> None:
        self._seed_with_orphan()
        first = prepare_audit_snapshot_scope_fix(
            workspace_root=_WS, database_path=_DB
        )
        backups = list((_WS / "zalohy").glob("pre_audit_snapshot_scope_fix_*"))
        second = prepare_audit_snapshot_scope_fix(
            workspace_root=_WS, database_path=_DB
        )
        self.assertFalse(second.migrated)
        self.assertEqual(second.skipped_reason, "transition_already_complete")
        self.assertEqual(
            list((_WS / "zalohy").glob("pre_audit_snapshot_scope_fix_*")),
            backups,
        )
        self.assertTrue(is_transition_complete(_WS, SCOPE_TRANSITION))
        self.assertTrue(scope_column_present(_DB))
        _ = first

    def test_classification_rollback_on_error(self) -> None:
        info = self._first_assertion(self.processes[0].id)
        audit = audit_service.create_audit(title="Fail")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=info[0],
                area_label=info[1],
                section_id=info[2],
                section_label=info[3],
                control_point_id=info[4],
                control_point_label="x",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        # Reset scope to NULL to force reclassification.
        conn = sqlite3.connect(str(_DB))
        try:
            conn.execute("UPDATE audit_question_snapshots SET is_in_scope = NULL")
            conn.commit()
        finally:
            conn.close()
        state = read_migration_state(_WS)
        state["completed_transitions"] = [
            item
            for item in (state.get("completed_transitions") or [])
            if item != SCOPE_TRANSITION
        ]
        write_migration_state(_WS, state)

        with patch(
            "moduly.audity.sluzby.audit_snapshot_scope_migration."
            "audit_question_snapshot_service.build_snapshot_for_audit",
            side_effect=RuntimeError("umělá chyba klasifikace"),
        ):
            with self.assertRaises(AuditSnapshotScopeFixError):
                prepare_audit_snapshot_scope_fix(
                    workspace_root=_WS, database_path=_DB
                )

        conn = sqlite3.connect(str(_DB))
        try:
            nulls = conn.execute(
                "SELECT COUNT(*) FROM audit_question_snapshots "
                "WHERE is_in_scope IS NULL"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(nulls, 0)
        self.assertFalse(is_transition_complete(_WS, SCOPE_TRANSITION))

    def test_completed_mismatch_reclassifies(self) -> None:
        self._seed_with_orphan()
        mark_migration_complete(_WS, backup_path=None, transition_id=SCOPE_TRANSITION)
        conn = sqlite3.connect(str(_DB))
        try:
            conn.execute("UPDATE audit_question_snapshots SET is_in_scope = NULL")
            conn.commit()
        finally:
            conn.close()
        result = prepare_audit_snapshot_scope_fix(
            workspace_root=_WS, database_path=_DB
        )
        self.assertTrue(result.migrated)
        conn = sqlite3.connect(str(_DB))
        try:
            nulls = conn.execute(
                "SELECT COUNT(*) FROM audit_question_snapshots "
                "WHERE is_in_scope IS NULL"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(nulls, 0)

    def test_live_audit_keeps_a12_3_orphan_filter(self) -> None:
        """Live audit: osiřelé CR mimo metodiku se v příloze neobjeví (9e318ad)."""
        info = self._first_assertion(self.processes[0].id)
        audit = audit_service.create_audit(title="Live")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=info[0],
                area_label=info[1],
                section_id=info[2],
                section_label=info[3],
                control_point_id=info[4],
                control_point_label="platné",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        # Orphan assertion ID v existující sekci — live filtr zahodí.
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=info[0],
                area_label=info[1],
                section_id=info[2],
                section_label=info[3],
                control_point_id="removed_from_methodology_xyz",
                control_point_label="LIVE ORPHAN",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        with get_session() as session:
            db = session.get(Audit, audit.id)
            db.methodology_source = None
            db.methodology_generation = None
            db.questions_frozen_at = None
            session.commit()
        ctx = AuditExportContext(audit=audit_service.get_by_id(audit.id))
        appendix = ctx.summary_appendix_assertions().plain_text()
        self.assertIn("platné", appendix)
        self.assertNotIn("LIVE ORPHAN", appendix)


if __name__ == "__main__":
    unittest.main()
