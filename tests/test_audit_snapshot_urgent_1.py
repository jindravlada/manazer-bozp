"""AUDIT-SNAPSHOT-URGENT-1: DB-only integrita + zapečetění manifestu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete, select

_TMP = Path(tempfile.mkdtemp(prefix="audit-snapshot-urgent-1-"))
_WS = _TMP / ".local" / "share" / "manazer-bozp"
_DB = _WS / "databaze" / "manager_bozp.db"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.shared.constants import (
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
    )
    from core.shared.modely.control_result import ControlResult
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from moduly.audity.constants import (
        AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
        AUDIT_METHODOLOGY_GENERATION_V2,
        AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
        AUDIT_QUESTION_KIND_OPERATION,
        AUDIT_QUESTION_KIND_SYSTEM,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_snapshot_backfill_service import (
        AUDIT_BACKFILL_STATUS_INCONSISTENT,
        AUDIT_BACKFILL_STATUS_LEGACY_COMPLETE,
        classify_audit_backfill_state,
        prepare_audit_snapshot_backfill,
    )
    from moduly.audity.sluzby.audit_snapshot_integrity_service import (
        BACKUP_NAME_PREFIX,
        TRANSITION_ID as INTEGRITY_TRANSITION,
        apply_snapshot_integrity_manifest,
        compute_snapshot_integrity_hash,
        diagnose_frozen_snapshot_db_only,
        prepare_audit_snapshot_integrity_seal,
    )
    from moduly.audity.sluzby.audit_snapshot_schema_migration import (
        prepare_audit_snapshot_schema,
    )
    from moduly.audity.sluzby.audit_snapshot_scope_migration import (
        ensure_scope_column,
        prepare_audit_snapshot_scope_fix,
    )
    from core.database.upgrade_guard import is_transition_complete


def _prepare_schema() -> None:
    prepare_audit_snapshot_schema(workspace_root=_WS, database_path=_DB)
    ensure_scope_column(_DB)


class AuditSnapshotUrgent1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(ControlResult))
            session.execute(delete(AuditQuestionSnapshot))
            session.execute(delete(Audit))
            session.commit()
        for path in (_WS / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"):
            path.unlink(missing_ok=True)
        _prepare_schema()

    def _backfill(self):
        return prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)

    def _seal(self):
        return prepare_audit_snapshot_integrity_seal(
            workspace_root=_WS, database_path=_DB
        )

    def _load_audit_bundle(self, audit_id: int):
        with get_session() as session:
            audit = session.get(Audit, audit_id)
            assert audit is not None
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit_id
                    )
                )
            )
            results = list(
                session.scalars(
                    select(ControlResult).where(
                        ControlResult.entity_type == ENTITY_AUDITY,
                        ControlResult.entity_id == audit_id,
                    )
                )
            )
            session.expunge(audit)
            for row in snaps:
                session.expunge(row)
            for row in results:
                session.expunge(row)
            return audit, snaps, results

    def test_json_question_kind_change_does_not_break_start(self) -> None:
        audit = audit_service.create_audit(title="Kind change")
        self._backfill()
        audit, snaps, results = self._load_audit_bundle(audit.id)
        self.assertEqual(
            classify_audit_backfill_state(
                audit,
                snapshot_rows=snaps,
                control_results=results,
                methodology_drafts=[],
            ).status,
            AUDIT_BACKFILL_STATUS_LEGACY_COMPLETE,
        )
        # Simulace změny živé metodiky — classify ji ignoruje.
        fake_drafts = []
        tree = audit_knowledge_service.get_knowledge_tree(ensure=False)
        for root in tree:
            for node in root.children:
                for q in audit_knowledge_service.get_audit_questions(node.section or {}):
                    q["question_kind"] = AUDIT_QUESTION_KIND_SYSTEM
        item = classify_audit_backfill_state(
            audit,
            snapshot_rows=snaps,
            control_results=results,
            methodology_drafts=fake_drafts,
        )
        self.assertEqual(item.status, AUDIT_BACKFILL_STATUS_LEGACY_COMPLETE)
        second = self._backfill()
        self.assertFalse(second.migrated)

    def test_many_snapshots_few_or_zero_results_valid(self) -> None:
        audit = audit_service.create_audit(title="Sparse CR")
        self._backfill()
        audit, snaps, results = self._load_audit_bundle(audit.id)
        self.assertGreater(len(snaps), 10)
        self.assertEqual(len(results), 0)
        reasons = diagnose_frozen_snapshot_db_only(
            audit,
            snapshot_rows=snaps,
            control_results=results,
            require_manifest=True,
        )
        self.assertEqual(reasons, [])

        # Přidej 2 výsledky — stále platné.
        first = snaps[0]
        second = snaps[1]
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                control_point_id=first.assertion_id,
                control_point_label=first.assertion_text,
                area_id=first.process_id,
                area_label=first.process_name,
                section_id=first.section_id,
                section_label=first.section_name,
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                control_point_id=second.assertion_id,
                control_point_label=second.assertion_text,
                area_id=second.process_id,
                area_label=second.process_name,
                section_id=second.section_id,
                section_label=second.section_name,
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        audit, snaps, results = self._load_audit_bundle(audit.id)
        self.assertEqual(len(results), 2)
        self.assertGreater(len(snaps), len(results))
        self.assertEqual(
            diagnose_frozen_snapshot_db_only(
                audit,
                snapshot_rows=snaps,
                control_results=results,
                require_manifest=True,
            ),
            [],
        )

    def test_missing_snapshot_for_control_result_precise_error(self) -> None:
        audit = audit_service.create_audit(title="Missing snap for CR")
        self._backfill()
        audit, snaps, _results = self._load_audit_bundle(audit.id)
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                control_point_id="orphan_only_cr",
                control_point_label="Orphan CR",
                area_id="missing_process",
                area_label="Missing",
                section_id="missing_section",
                section_label="Missing",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        audit, snaps, results = self._load_audit_bundle(audit.id)
        reasons = diagnose_frozen_snapshot_db_only(
            audit,
            snapshot_rows=snaps,
            control_results=results,
            require_manifest=True,
        )
        self.assertTrue(any("control_result" in r for r in reasons))
        item = classify_audit_backfill_state(
            audit, snapshot_rows=snaps, control_results=results
        )
        self.assertEqual(item.status, AUDIT_BACKFILL_STATUS_INCONSISTENT)
        self.assertIn("control_result", item.detail)

    def test_null_is_in_scope_precise_error(self) -> None:
        audit = audit_service.create_audit(title="Null scope")
        self._backfill()
        with get_session() as session:
            snap = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id
                )
            )
            assert snap is not None
            snap.is_in_scope = None
            session.commit()
        audit, snaps, results = self._load_audit_bundle(audit.id)
        reasons = diagnose_frozen_snapshot_db_only(
            audit,
            snapshot_rows=snaps,
            control_results=results,
            require_manifest=True,
        )
        self.assertTrue(any("is_in_scope IS NULL" in r for r in reasons))

    def test_hash_mismatch_after_seal_when_row_deleted(self) -> None:
        audit = audit_service.create_audit(title="Hash mismatch")
        self._backfill()
        with get_session() as session:
            snap = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id
                )
            )
            assert snap is not None
            session.delete(snap)
            session.commit()
        with self.assertRaises(Exception) as ctx:
            self._backfill()
        self.assertIn("nekonzistentní", str(ctx.exception).lower())
        self.assertIn("hash", str(ctx.exception).lower())

    def test_json_change_does_not_change_hash(self) -> None:
        audit = audit_service.create_audit(title="Hash stable")
        self._backfill()
        audit, snaps, _r = self._load_audit_bundle(audit.id)
        before = audit.snapshot_integrity_hash
        for root in audit_knowledge_service.get_knowledge_tree(ensure=False):
            for node in root.children:
                for q in audit_knowledge_service.get_audit_questions(node.section or {}):
                    q["text"] = "Změněný text otázky"
                    q["question_kind"] = AUDIT_QUESTION_KIND_OPERATION
                    q["active"] = False
        audit2, snaps2, _r2 = self._load_audit_bundle(audit.id)
        self.assertEqual(before, audit2.snapshot_integrity_hash)
        self.assertEqual(before, compute_snapshot_integrity_hash(snaps2))

    def test_seal_existing_without_manifest_creates_backup(self) -> None:
        audit = audit_service.create_audit(title="Needs seal")
        self._backfill()
        with get_session() as session:
            row = session.get(Audit, audit.id)
            assert row is not None
            row.snapshot_question_count = None
            row.snapshot_integrity_hash = None
            session.commit()
        # Zneplatni complete marker integrity, ať seal znovu běží.
        from core.database.upgrade_guard import clear_transition_complete

        clear_transition_complete(_WS, INTEGRITY_TRANSITION)
        backups_before = list((_WS / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        result = self._seal()
        self.assertTrue(result.migrated)
        self.assertEqual(result.sealed_audits, 1)
        self.assertIsNotNone(result.pre_migration_backup_path)
        self.assertTrue(result.pre_migration_backup_path.is_file())
        backups_after = list((_WS / "zalohy").glob(f"{BACKUP_NAME_PREFIX}_*"))
        self.assertGreater(len(backups_after), len(backups_before))
        audit, snaps, results = self._load_audit_bundle(audit.id)
        self.assertEqual(audit.snapshot_question_count, len(snaps))
        self.assertTrue(audit.snapshot_integrity_hash)
        self.assertEqual(
            diagnose_frozen_snapshot_db_only(
                audit, snapshot_rows=snaps, control_results=results, require_manifest=True
            ),
            [],
        )
        # Opakovaný start = no-op.
        second = self._seal()
        self.assertFalse(second.migrated)
        self.assertEqual(second.sealed_audits, 0)

    def test_seal_failure_rolls_back(self) -> None:
        audit = audit_service.create_audit(title="Seal fail")
        self._backfill()
        with get_session() as session:
            row = session.get(Audit, audit.id)
            assert row is not None
            row.snapshot_question_count = None
            row.snapshot_integrity_hash = None
            snap = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id
                )
            )
            assert snap is not None
            snap.is_in_scope = None
            session.commit()
        from core.database.upgrade_guard import clear_transition_complete

        clear_transition_complete(_WS, INTEGRITY_TRANSITION)
        with self.assertRaises(Exception) as ctx:
            self._seal()
        self.assertIn("is_in_scope IS NULL", str(ctx.exception))
        audit, _snaps, _r = self._load_audit_bundle(audit.id)
        self.assertIsNone(audit.snapshot_question_count)
        self.assertFalse(audit.snapshot_integrity_hash)

    def test_other_generation_untouched_by_legacy_guard(self) -> None:
        legacy = audit_service.create_audit(title="Legacy gen")
        future = audit_service.create_audit(title="Future gen")
        self._backfill()
        frozen = datetime(2030, 1, 2, 3, 4, 5)
        with get_session() as session:
            fut = session.get(Audit, future.id)
            assert fut is not None
            fut.methodology_generation = "future-v9"
            fut.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
            fut.questions_frozen_at = frozen
            for row in list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == future.id
                    )
                )
            ):
                session.delete(row)
            session.flush()
            session.add(
                AuditQuestionSnapshot(
                    audit_id=future.id,
                    process_id="future_p",
                    process_name="Future process",
                    section_id="future_s",
                    section_name="Future section",
                    assertion_id="future_q",
                    assertion_text="Future question",
                    verification_type="dokumentace",
                    severity="stredni",
                    question_kind="future",
                    display_order=1,
                    is_in_scope=True,
                    created_at=frozen,
                )
            )
            fut.snapshot_question_count = None
            fut.snapshot_integrity_hash = None
            session.commit()
        from core.database.upgrade_guard import clear_transition_complete

        clear_transition_complete(_WS, INTEGRITY_TRANSITION)
        seal = self._seal()
        self.assertGreaterEqual(seal.sealed_audits, 1)
        future_reloaded, snaps, results = self._load_audit_bundle(future.id)
        self.assertEqual(future_reloaded.methodology_generation, "future-v9")
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].assertion_text, "Future question")
        item = classify_audit_backfill_state(
            future_reloaded, snapshot_rows=snaps, control_results=results
        )
        self.assertEqual(item.status, "other_generation")
        legacy_reloaded, lsnaps, lresults = self._load_audit_bundle(legacy.id)
        self.assertEqual(
            classify_audit_backfill_state(
                legacy_reloaded, snapshot_rows=lsnaps, control_results=lresults
            ).status,
            AUDIT_BACKFILL_STATUS_LEGACY_COMPLETE,
        )


if __name__ == "__main__":
    unittest.main()
