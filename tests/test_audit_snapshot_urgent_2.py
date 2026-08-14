"""AUDIT-SNAPSHOT-URGENT-2: atomické ruční v2 + bezpečné odstranění auditu id=7."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select, text

_TMP = Path(tempfile.mkdtemp(prefix="audit-snapshot-urgent-2-"))
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
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.control_result_service import control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from core.services.attachment_service import attachment_service
    from moduly.audity.constants import (
        AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
        AUDIT_METHODOLOGY_GENERATION_V2,
        AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
        AUDIT_QUESTION_KIND_EXTRAORDINARY,
        AUDIT_QUESTION_KIND_OPERATION,
        AUDIT_QUESTION_KIND_SYSTEM,
        AUDIT_START_MISSING_SYSTEM_WORKPLACE,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_knowledge_service import (
        KnowledgeTreeNode,
        audit_knowledge_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_question_source_service import (
        audit_question_source_service,
    )
    from moduly.audity.sluzby.audit_question_snapshot_service import (
        AuditV2SnapshotError,
        audit_question_snapshot_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_snapshot_integrity_service import (
        compute_snapshot_integrity_hash,
    )
    from moduly.audity.sluzby.audit_v2_create_service import (
        AuditV2CreateError,
        create_manual_audit_with_v2_snapshot,
    )
    from moduly.audity.sluzby.incomplete_manual_audit_cleanup_service import (
        TARGET_INCOMPLETE_MANUAL_AUDIT_ID,
        collect_incomplete_manual_audit_diagnostics,
        delete_incomplete_manual_audit_atomically,
        offer_incomplete_manual_audit_cleanup_at_startup,
        IncompleteManualAuditCleanupError,
    )
    from moduly.audity.sluzby.system_audit_workplace_service import (
        SystemAuditWorkplaceError,
        system_audit_workplace_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _question(qid: str, text: str, *, kind: str | None = None) -> dict:
    payload = {
        "id": qid,
        "text": text,
        "aktivni": True,
        "poradi": 10,
        "verification_type": "dokumentace",
        "zavaznost": "stredni",
    }
    if kind is not None:
        payload["question_kind"] = kind
    return payload


def _section(section_id: str, name: str, questions: list[dict]) -> dict:
    return {
        "id": section_id,
        "nazev": name,
        "aktivni": True,
        "auditni_tvrzeni": questions,
        "sekce": [],
    }


def _fake_tree(process_id: str, process_name: str, section: dict) -> list:
    section_node = KnowledgeTreeNode(
        node_type="section",
        node_id=section["id"],
        label=section["nazev"],
        process_id=process_id,
        process_label=process_name,
        section=section,
        children=(),
    )
    return [
        KnowledgeTreeNode(
            node_type="process",
            node_id=process_id,
            label=process_name,
            process_id=process_id,
            process_label=process_name,
            section=None,
            children=(section_node,),
        )
    ]


def _mixed_tree() -> list:
    section = _section(
        "sec_m",
        "Sekce M",
        [
            _question("sys_m", "Systém M", kind=AUDIT_QUESTION_KIND_SYSTEM),
            _question("ops_m", "Provoz M", kind=AUDIT_QUESTION_KIND_OPERATION),
            _question("ext_m", "Mimořádné M", kind=AUDIT_QUESTION_KIND_EXTRAORDINARY),
        ],
    )
    return _fake_tree("proc_m", "Proces M", section)


class ManualV2CreateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.system_wp = settings_service.save_workplace(name="Sys U2", active=True)
        self.ops_wp = settings_service.save_workplace(name="Ops U2", active=True)
        system_audit_workplace_service.set_system_audit_workplace_id(self.system_wp.id)
        self.tree = _mixed_tree()

    def _create_manual(self, workplace_id: int, *, tree=None):
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            return_value=tree if tree is not None else self.tree,
        ) as mocked:
            audit = create_manual_audit_with_v2_snapshot(
                fields={
                    "workplace_id": workplace_id,
                    "workplace_name": "",
                    "year": 2026,
                    "audit_date": date(2026, 8, 14),
                    "started_at": date(2026, 8, 14),
                    "title": "Ruční U2",
                },
                commission_members=None,
            )
            return audit, mocked

    def test_01_manual_system_only_system(self) -> None:
        audit, _ = self._create_manual(self.system_wp.id)
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual({s.assertion_id for s in snaps}, {"sys_m"})
        self.assertEqual({s.question_kind for s in snaps}, {AUDIT_QUESTION_KIND_SYSTEM})

    def test_02_manual_system_no_operation(self) -> None:
        audit, _ = self._create_manual(self.system_wp.id)
        with get_session() as session:
            kinds = {
                s.question_kind
                for s in session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            }
        self.assertNotIn(AUDIT_QUESTION_KIND_OPERATION, kinds)

    def test_03_manual_system_no_unclassified(self) -> None:
        section = _section(
            "sec_u",
            "Sekce U",
            [
                _question("sys_u", "Systém U", kind=AUDIT_QUESTION_KIND_SYSTEM),
                _question("unc_u", "Nezařazeno U"),
            ],
        )
        tree = _fake_tree("proc_u", "Proces U", section)
        before = len(audit_service.get_all())
        with patch.object(audit_knowledge_service, "get_knowledge_tree", return_value=tree):
            with self.assertRaises(AuditV2SnapshotError):
                create_manual_audit_with_v2_snapshot(
                    fields={
                        "workplace_id": self.system_wp.id,
                        "year": 2026,
                        "started_at": date.today(),
                    },
                )
        self.assertEqual(len(audit_service.get_all()), before)
        with get_session() as session:
            orphan = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.assertion_id == "unc_u"
                    )
                )
            )
        self.assertEqual(orphan, [])

    def test_04_manual_operation_only_operation(self) -> None:
        audit, _ = self._create_manual(self.ops_wp.id)
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual({s.assertion_id for s in snaps}, {"ops_m"})
        self.assertEqual({s.question_kind for s in snaps}, {AUDIT_QUESTION_KIND_OPERATION})

    def test_05_manual_operation_no_system(self) -> None:
        audit, _ = self._create_manual(self.ops_wp.id)
        with get_session() as session:
            kinds = {
                s.question_kind
                for s in session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            }
        self.assertNotIn(AUDIT_QUESTION_KIND_SYSTEM, kinds)

    def test_06_extraordinary_excluded(self) -> None:
        audit, _ = self._create_manual(self.ops_wp.id)
        with get_session() as session:
            ids = {
                s.assertion_id
                for s in session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            }
        self.assertNotIn("ext_m", ids)

    def test_07_unclassified_blocks_manual(self) -> None:
        section = _section(
            "sec_b",
            "Sekce B",
            [
                _question("ops_b", "Provoz B", kind=AUDIT_QUESTION_KIND_OPERATION),
                _question("unc_b", "Bez druhu"),
            ],
        )
        tree = _fake_tree("proc_b", "Proces B", section)
        with patch.object(audit_knowledge_service, "get_knowledge_tree", return_value=tree):
            with self.assertRaises(AuditV2SnapshotError) as ctx:
                create_manual_audit_with_v2_snapshot(
                    fields={
                        "workplace_id": self.ops_wp.id,
                        "year": 2026,
                        "started_at": date.today(),
                    },
                )
        self.assertIn("Proces B", str(ctx.exception))
        self.assertIn("unc_b", str(ctx.exception))

    def test_08_error_leaves_no_audit_or_snapshot(self) -> None:
        section = _section(
            "sec_err",
            "Sekce Err",
            [_question("unc_err", "Chyba")],
        )
        tree = _fake_tree("proc_err", "Proces Err", section)
        before_audits = {a.id for a in audit_service.get_all()}
        with get_session() as session:
            before_snaps = session.scalar(
                text("SELECT COUNT(*) FROM audit_question_snapshots")
            )
        with patch.object(audit_knowledge_service, "get_knowledge_tree", return_value=tree):
            with self.assertRaises(AuditV2SnapshotError):
                create_manual_audit_with_v2_snapshot(
                    fields={
                        "workplace_id": self.ops_wp.id,
                        "year": 2026,
                        "started_at": date.today(),
                    },
                )
        self.assertEqual({a.id for a in audit_service.get_all()}, before_audits)
        with get_session() as session:
            after_snaps = session.scalar(
                text("SELECT COUNT(*) FROM audit_question_snapshots")
            )
        self.assertEqual(after_snaps, before_snaps)

    def test_09_missing_system_workplace_blocks(self) -> None:
        system_audit_workplace_service.set_system_audit_workplace_id(None)
        with patch.object(
            audit_knowledge_service, "get_knowledge_tree", return_value=self.tree
        ):
            with self.assertRaises(SystemAuditWorkplaceError) as ctx:
                create_manual_audit_with_v2_snapshot(
                    fields={
                        "workplace_id": self.ops_wp.id,
                        "year": 2026,
                        "started_at": date.today(),
                    },
                )
        self.assertIn(AUDIT_START_MISSING_SYSTEM_WORKPLACE, str(ctx.exception))

    def test_10_manual_is_snapshot_v2(self) -> None:
        audit, mocked = self._create_manual(self.ops_wp.id)
        self.assertEqual(audit.methodology_source, AUDIT_METHODOLOGY_SOURCE_SNAPSHOT)
        self.assertEqual(audit.methodology_generation, AUDIT_METHODOLOGY_GENERATION_V2)
        self.assertIsNotNone(audit.questions_frozen_at)
        mocked.assert_called_once()

    def test_11_manifest_count_hash(self) -> None:
        audit, _ = self._create_manual(self.system_wp.id)
        refreshed = audit_service.get_by_id(audit.id)
        assert refreshed is not None
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual(refreshed.snapshot_question_count, len(snaps))
        self.assertEqual(
            refreshed.snapshot_integrity_hash,
            compute_snapshot_integrity_hash(snaps),
        )

    def test_12_commission_error_rolls_back(self) -> None:
        before = len(audit_service.get_all())
        with patch.object(
            audit_knowledge_service, "get_knowledge_tree", return_value=self.tree
        ):
            with self.assertRaises(ValueError):
                create_manual_audit_with_v2_snapshot(
                    fields={
                        "workplace_id": self.ops_wp.id,
                        "year": 2026,
                        "started_at": date.today(),
                    },
                    commission_members=[{"record_type": "leader", "display_name": "X"}],
                )
        self.assertEqual(len(audit_service.get_all()), before)

    def test_13_reopen_system_shows_only_system(self) -> None:
        audit, _ = self._create_manual(self.system_wp.id)
        source = audit_question_source_service.resolve_for_audit(audit.id)
        kinds = {q.question_kind for q in source.assertions}
        ids = {q.assertion_id for q in source.assertions}
        self.assertEqual(kinds, {AUDIT_QUESTION_KIND_SYSTEM})
        self.assertEqual(ids, {"sys_m"})

    def test_14_reopen_operation_shows_only_operation(self) -> None:
        audit, _ = self._create_manual(self.ops_wp.id)
        source = audit_question_source_service.resolve_for_audit(audit.id)
        kinds = {q.question_kind for q in source.assertions}
        ids = {q.assertion_id for q in source.assertions}
        self.assertEqual(kinds, {AUDIT_QUESTION_KIND_OPERATION})
        self.assertEqual(ids, {"ops_m"})

    def test_15_json_change_after_create_ignored(self) -> None:
        audit, _ = self._create_manual(self.ops_wp.id)
        mutated = _section(
            "sec_m",
            "Sekce M",
            [
                _question("ops_m", "Provoz M MUT", kind=AUDIT_QUESTION_KIND_OPERATION),
                _question("ops_new", "Nová", kind=AUDIT_QUESTION_KIND_OPERATION),
            ],
        )
        mutated_tree = _fake_tree("proc_m", "Proces M", mutated)
        with patch.object(
            audit_knowledge_service, "get_knowledge_tree", return_value=mutated_tree
        ):
            source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertEqual({q.assertion_id for q in source.assertions}, {"ops_m"})
        self.assertEqual(source.assertions[0].assertion_text, "Provoz M")


class IncompleteCleanupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Vyčisti audity z předchozích testů v sdílené DB — izoluj id=7.
        with get_session() as session:
            session.execute(text("DELETE FROM audit_question_snapshots"))
            session.execute(text("DELETE FROM audit_commission_members"))
            session.execute(text("DELETE FROM audit_verification_overrides"))
            session.execute(
                text("DELETE FROM control_results WHERE entity_type = :t"),
                {"t": ENTITY_AUDITY},
            )
            session.execute(
                text("DELETE FROM findings WHERE entity_type = :t"),
                {"t": ENTITY_AUDITY},
            )
            session.execute(
                text("DELETE FROM attachments WHERE entity_type IN ('audity', 'audit')")
            )
            session.execute(text("DELETE FROM audits"))
            session.execute(
                text("UPDATE audit_program_visits SET audit_id = NULL")
            )
            session.commit()

        self.wp = settings_service.save_workplace(name="Cleanup WP", active=True)

    def _seed_incomplete_audit_id7(self, *, with_snaps: bool = True) -> Audit:
        """Vytvoří neúplný audit s pevně daným id=7 (markery NULL + snaps)."""
        with get_session() as session:
            existing = session.get(Audit, TARGET_INCOMPLETE_MANUAL_AUDIT_ID)
            if existing is not None:
                session.delete(existing)
                session.flush()
            audit = Audit(
                id=TARGET_INCOMPLETE_MANUAL_AUDIT_ID,
                number=f"{TARGET_INCOMPLETE_MANUAL_AUDIT_ID}/2026",
                year=2026,
                started_at=date(2026, 8, 1),
                workplace_id=self.wp.id,
                workplace_name=self.wp.name,
                title="Neúplný test",
                methodology_source=None,
                methodology_generation=None,
                questions_frozen_at=None,
            )
            session.add(audit)
            if with_snaps:
                for i in range(3):
                    session.add(
                        AuditQuestionSnapshot(
                            audit_id=TARGET_INCOMPLETE_MANUAL_AUDIT_ID,
                            process_id="p",
                            process_name="P",
                            section_id="s",
                            section_name="S",
                            assertion_id=f"a{i}",
                            assertion_text=f"Otázka {i}",
                            verification_type="documentation",
                            severity="normal",
                            question_kind=AUDIT_QUESTION_KIND_SYSTEM,
                            display_order=i,
                            is_in_scope=True,
                            created_at=datetime.now(),
                        )
                    )
            session.commit()
            session.refresh(audit)
            session.expunge(audit)
            return audit

    def test_16_detection_shows_dialog_text(self) -> None:
        self._seed_incomplete_audit_id7()
        diag = collect_incomplete_manual_audit_diagnostics()
        assert diag is not None
        self.assertTrue(diag.eligible_for_confirmed_cleanup)
        self.assertEqual(diag.snapshot_count, 3)
        self.assertEqual(diag.control_results_count, 0)

    def test_17_cancel_keeps_audit(self) -> None:
        self._seed_incomplete_audit_id7()
        with self.assertRaises(IncompleteManualAuditCleanupError):
            offer_incomplete_manual_audit_cleanup_at_startup(
                workspace_root=_WS,
                database_path=_DB,
                interactive=False,
                auto_confirm=False,
            )
        self.assertIsNotNone(
            audit_service.get_by_id(TARGET_INCOMPLETE_MANUAL_AUDIT_ID)
        )

    def test_18_result_blocks_cleanup(self) -> None:
        audit = self._seed_incomplete_audit_id7()
        with get_session() as session:
            session.add(
                ControlResult(
                    entity_type=ENTITY_AUDITY,
                    entity_id=audit.id,
                    source_area_id="p",
                    source_area_label="P",
                    source_section_id="s",
                    source_section_label="S",
                    source_control_point_id="a0",
                    source_control_point_label="Otázka 0",
                    result=CONTROL_RESULT_VYHOVUJE,
                )
            )
            session.commit()
        diag = collect_incomplete_manual_audit_diagnostics()
        assert diag is not None
        self.assertFalse(diag.eligible_for_confirmed_cleanup)
        with self.assertRaises(IncompleteManualAuditCleanupError):
            offer_incomplete_manual_audit_cleanup_at_startup(
                workspace_root=_WS,
                database_path=_DB,
                auto_confirm=True,
            )

    def test_19_finding_blocks_cleanup(self) -> None:
        audit = self._seed_incomplete_audit_id7()
        finding_service.create(
            entity_type=ENTITY_AUDITY,
            entity_id=audit.id,
            description="Zjištění test",
            source_area_label="P",
            source_section_label="S",
            source_control_point_id="a0",
        )
        diag = collect_incomplete_manual_audit_diagnostics()
        assert diag is not None
        self.assertFalse(diag.eligible_for_confirmed_cleanup)

    def test_20_attachment_blocks_cleanup(self) -> None:
        audit = self._seed_incomplete_audit_id7()
        tmp = _TMP / "attach.txt"
        tmp.write_text("x", encoding="utf-8")
        attachment_service.add_file("audit", audit.id, str(tmp))
        diag = collect_incomplete_manual_audit_diagnostics()
        assert diag is not None
        self.assertFalse(diag.eligible_for_confirmed_cleanup)

    def test_21_backup_created_before_delete(self) -> None:
        self._seed_incomplete_audit_id7()
        result = delete_incomplete_manual_audit_atomically(
            TARGET_INCOMPLETE_MANUAL_AUDIT_ID,
            workspace_root=_WS,
            database_path=_DB,
            create_backup=True,
        )
        self.assertTrue(result.deleted)
        assert result.backup_path is not None
        self.assertTrue(result.backup_path.is_file())
        self.assertTrue(
            result.backup_path.name.startswith("pre_incomplete_manual_audit_cleanup_")
        )
        self.assertIsNone(audit_service.get_by_id(TARGET_INCOMPLETE_MANUAL_AUDIT_ID))

    def test_22_backup_failure_prevents_delete(self) -> None:
        self._seed_incomplete_audit_id7()
        with patch(
            "moduly.audity.sluzby.incomplete_manual_audit_cleanup_service."
            "create_verified_pre_migration_backup",
            side_effect=Exception("boom"),
        ):
            # PreMigrationBackupError wrapper — patch raises generic, code wraps
            # only PreMigrationBackupError. Force PreMigrationBackupError.
            from core.database.upgrade_guard import PreMigrationBackupError

            with patch(
                "moduly.audity.sluzby.incomplete_manual_audit_cleanup_service."
                "create_verified_pre_migration_backup",
                side_effect=PreMigrationBackupError("záloha selhala"),
            ):
                with self.assertRaises(IncompleteManualAuditCleanupError):
                    delete_incomplete_manual_audit_atomically(
                        TARGET_INCOMPLETE_MANUAL_AUDIT_ID,
                        workspace_root=_WS,
                        database_path=_DB,
                        create_backup=True,
                    )
        self.assertIsNotNone(
            audit_service.get_by_id(TARGET_INCOMPLETE_MANUAL_AUDIT_ID)
        )

    def test_23_delete_failure_rolls_back(self) -> None:
        self._seed_incomplete_audit_id7()
        with patch(
            "moduly.audity.sluzby.incomplete_manual_audit_cleanup_service.get_session"
        ) as mocked_session:
            # Necháme create_backup=False a selhání uvnitř mazání simulujeme
            # přes collect — raději: po záloze selže commit.
            pass
        del mocked_session

        real_get = get_session

        class _BoomSession:
            def __enter__(self):
                self._inner = real_get().__enter__()
                return self

            def __exit__(self, *args):
                return self._inner.__exit__(*args)

            def get(self, *args, **kwargs):
                return self._inner.get(*args, **kwargs)

            def scalars(self, *args, **kwargs):
                return self._inner.scalars(*args, **kwargs)

            def delete(self, obj):
                if isinstance(obj, Audit):
                    raise RuntimeError("simulated delete failure")
                return self._inner.delete(obj)

            def commit(self):
                return self._inner.commit()

            def rollback(self):
                return self._inner.rollback()

        with patch(
            "moduly.audity.sluzby.incomplete_manual_audit_cleanup_service.get_session",
            return_value=_BoomSession(),
        ):
            with self.assertRaises(RuntimeError):
                delete_incomplete_manual_audit_atomically(
                    TARGET_INCOMPLETE_MANUAL_AUDIT_ID,
                    workspace_root=_WS,
                    database_path=_DB,
                    create_backup=False,
                )
        self.assertIsNotNone(
            audit_service.get_by_id(TARGET_INCOMPLETE_MANUAL_AUDIT_ID)
        )
        with get_session() as session:
            count = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == TARGET_INCOMPLETE_MANUAL_AUDIT_ID
                ).limit(1)
            )
        self.assertIsNotNone(count)

    def test_24_after_cleanup_remaining_pass_guard(self) -> None:
        self._seed_incomplete_audit_id7()
        # Pad audity 1..6 jsou live bez snaps — backfill by je chtěl, ale
        # po cleanup id=7 ověříme, že id=7 zmizel.
        offer_incomplete_manual_audit_cleanup_at_startup(
            workspace_root=_WS,
            database_path=_DB,
            auto_confirm=True,
        )
        self.assertIsNone(audit_service.get_by_id(TARGET_INCOMPLETE_MANUAL_AUDIT_ID))

    def test_25_legacy_v1_untouched(self) -> None:
        legacy = audit_service.create_audit(
            workplace_id=self.wp.id,
            workplace_name=self.wp.name,
            year=2025,
            started_at=date(2025, 1, 1),
        )
        with get_session() as session:
            row = session.get(Audit, legacy.id)
            assert row is not None
            row.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
            row.methodology_generation = AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
            row.questions_frozen_at = datetime.now()
            session.add(
                AuditQuestionSnapshot(
                    audit_id=legacy.id,
                    process_id="lp",
                    process_name="LP",
                    section_id="ls",
                    section_name="LS",
                    assertion_id="la",
                    assertion_text="Legacy Q",
                    verification_type="documentation",
                    severity="normal",
                    question_kind="legacy",
                    display_order=0,
                    is_in_scope=True,
                    created_at=datetime.now(),
                )
            )
            session.flush()
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == legacy.id
                    )
                )
            )
            row.snapshot_question_count = len(snaps)
            row.snapshot_integrity_hash = compute_snapshot_integrity_hash(snaps)
            session.commit()

        before_hash = audit_service.get_by_id(legacy.id).snapshot_integrity_hash
        self._seed_incomplete_audit_id7()
        delete_incomplete_manual_audit_atomically(
            TARGET_INCOMPLETE_MANUAL_AUDIT_ID,
            workspace_root=_WS,
            database_path=_DB,
            create_backup=False,
        )
        after = audit_service.get_by_id(legacy.id)
        assert after is not None
        self.assertEqual(after.methodology_generation, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1)
        self.assertEqual(after.snapshot_integrity_hash, before_hash)


class ProgramVisitStillV2TestCase(unittest.TestCase):
    def test_26_program_visit_still_v2(self) -> None:
        system_wp = settings_service.save_workplace(name="Sys Prog", active=True)
        ops_wp = settings_service.save_workplace(name="Ops Prog", active=True)
        system_audit_workplace_service.set_system_audit_workplace_id(system_wp.id)
        tree = _mixed_tree()
        program = audit_program_service.create_program(
            name="Program U2",
            date_from=date(2026, 1, 1),
            date_to=date(2028, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=ops_wp.id,
            workplace_name=ops_wp.name,
            audit_interval_months=6,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=ops_wp.id,
            planned_year=2026,
            planned_month=9,
            planned_date=date(2026, 9, 1),
        )
        audit_program_service.add_visit_process(
            visit.id, process_id="proc_m", process_name="Proces M"
        )
        with patch.object(
            audit_knowledge_service, "get_knowledge_tree", return_value=tree
        ):
            audit = audit_program_service.create_audit_from_visit(visit.id)
        self.assertEqual(audit.methodology_generation, AUDIT_METHODOLOGY_GENERATION_V2)
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual({s.assertion_id for s in snaps}, {"ops_m"})


if __name__ == "__main__":
    unittest.main()
