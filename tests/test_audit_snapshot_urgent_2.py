"""AUDIT-SNAPSHOT-URGENT-2-cleanup: atomické ruční v2 + obecný guard bez id=7."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select, text

_TMP = Path(tempfile.mkdtemp(prefix="audit-snapshot-urgent-2-cleanup-"))
_WS = _TMP / ".local" / "share" / "manazer-bozp"
_DB = _WS / "databaze" / "manager_bozp.db"
_REPO = Path(__file__).resolve().parents[1]
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
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_snapshot_backfill_service import (
        AUDIT_BACKFILL_STATUS_INCONSISTENT,
        AuditSnapshotBackfillError,
        classify_audit_backfill_state,
        prepare_audit_snapshot_backfill,
    )
    from moduly.audity.sluzby.audit_snapshot_integrity_service import (
        compute_snapshot_integrity_hash,
    )
    from moduly.audity.sluzby.audit_snapshot_schema_migration import (
        prepare_audit_snapshot_schema,
    )
    from moduly.audity.sluzby.audit_v2_create_service import (
        create_manual_audit_with_v2_snapshot,
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


def _prepare_snapshot_schema() -> None:
    prepare_audit_snapshot_schema(workspace_root=_WS, database_path=_DB)


class NoHardcodedId7TestCase(unittest.TestCase):
    """Ve zdrojovém kódu nesmí zůstat speciální logika pro audit id=7."""

    _SCAN_PATHS = (
        _REPO / "core" / "database" / "upgrade_guard.py",
        _REPO / "moduly" / "audity" / "sluzby" / "audit_v2_create_service.py",
        _REPO / "moduly" / "audity" / "sluzby" / "audit_program_service.py",
        _REPO / "moduly" / "audity" / "sluzby" / "audit_service.py",
        _REPO / "moduly" / "audity" / "ui" / "audit_dialog.py",
    )

    def test_01_no_hardcoded_audit_id_7_in_production(self) -> None:
        cleanup_module = (
            _REPO
            / "moduly"
            / "audity"
            / "sluzby"
            / "incomplete_manual_audit_cleanup_service.py"
        )
        self.assertFalse(
            cleanup_module.is_file(),
            "Jednorázová cleanup služba pro id=7 musí být odstraněna.",
        )

        banned_snippets = (
            "TARGET_INCOMPLETE_MANUAL_AUDIT_ID",
            "pre_incomplete_manual_audit_cleanup",
            "Odstranit neúplný testovací audit",
            "offer_incomplete_manual_audit_cleanup_at_startup",
            "incomplete_manual_audit_cleanup_service",
            "TARGET_INCOMPLETE_MANUAL_AUDIT_ID = 7",
            "audit id=7",
            "auditu id=7",
            "id=7",
        )
        # Produkční soubory — žádná zmínka o jednorázovém testovacím id=7.
        for path in self._SCAN_PATHS:
            text_src = path.read_text(encoding="utf-8")
            for snippet in banned_snippets:
                self.assertNotIn(
                    snippet,
                    text_src,
                    f"{path.name} stále obsahuje {snippet!r}",
                )


class ManualV2CreateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.system_wp = settings_service.save_workplace(name="Sys U2c", active=True)
        self.ops_wp = settings_service.save_workplace(name="Ops U2c", active=True)
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
                    "title": "Ruční U2c",
                },
                commission_members=None,
                scope_processes=[
                    {
                        "process_id": "proc_m",
                        "process_name": "Proces M",
                        "display_order": 0,
                    }
                ],
            )
            audit = audit_program_service.prepare_audit_from_visit(audit.id)
            return audit, mocked

    def test_06_manual_system_only_system(self) -> None:
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

    def test_07_manual_operation_only_operation(self) -> None:
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

    def test_08_unclassified_blocks_manual(self) -> None:
        section = _section(
            "sec_b",
            "Sekce B",
            [
                _question("ops_b", "Provoz B", kind=AUDIT_QUESTION_KIND_OPERATION),
                _question("unc_b", "Bez druhu"),
            ],
        )
        tree = _fake_tree("proc_b", "Proces B", section)
        before = len(audit_service.get_all())
        with patch.object(audit_knowledge_service, "get_knowledge_tree", return_value=tree):
            audit = create_manual_audit_with_v2_snapshot(
                fields={
                    "workplace_id": self.ops_wp.id,
                    "year": 2026,
                    "started_at": date.today(),
                },
                scope_processes=[
                    {"process_id": "proc_b", "process_name": "Proces B"}
                ],
            )
            with self.assertRaises(AuditV2SnapshotError) as ctx:
                audit_program_service.prepare_audit_from_visit(audit.id)
        self.assertIn("Proces B", str(ctx.exception))
        self.assertIn("unc_b", str(ctx.exception))
        self.assertEqual(len(audit_service.get_all()), before + 1)
        self.assertIsNone(audit_service.get_by_id(audit.id).questions_frozen_at)

    def test_09_error_leaves_no_audit_or_snapshot(self) -> None:
        section = _section(
            "sec_err",
            "Sekce Err",
            [_question("unc_err", "Chyba")],
        )
        tree = _fake_tree("proc_err", "Proces Err", section)
        before_audits = {a.id for a in audit_service.get_all()}
        with get_session() as session:
            before_snaps = int(
                session.scalar(text("SELECT COUNT(*) FROM audit_question_snapshots"))
                or 0
            )
        with patch.object(audit_knowledge_service, "get_knowledge_tree", return_value=tree):
            audit = create_manual_audit_with_v2_snapshot(
                fields={
                    "workplace_id": self.ops_wp.id,
                    "year": 2026,
                    "started_at": date.today(),
                },
                scope_processes=[
                    {"process_id": "proc_err", "process_name": "Proces Err"}
                ],
            )
            with self.assertRaises(AuditV2SnapshotError):
                audit_program_service.prepare_audit_from_visit(audit.id)
        self.assertEqual({a.id for a in audit_service.get_all()}, before_audits | {audit.id})
        with get_session() as session:
            after_snaps = int(
                session.scalar(text("SELECT COUNT(*) FROM audit_question_snapshots"))
                or 0
            )
        self.assertEqual(after_snaps, before_snaps)

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

    def test_missing_system_workplace_blocks(self) -> None:
        system_audit_workplace_service.set_system_audit_workplace_id(None)
        with patch.object(
            audit_knowledge_service, "get_knowledge_tree", return_value=self.tree
        ):
            audit = create_manual_audit_with_v2_snapshot(
                fields={
                    "workplace_id": self.ops_wp.id,
                    "year": 2026,
                    "started_at": date.today(),
                },
                scope_processes=[
                    {"process_id": "proc_m", "process_name": "Proces M"}
                ],
            )
            with self.assertRaises(SystemAuditWorkplaceError) as ctx:
                audit_program_service.prepare_audit_from_visit(audit.id)
        self.assertIn(AUDIT_START_MISSING_SYSTEM_WORKPLACE, str(ctx.exception))

    def test_reopen_system_shows_only_system(self) -> None:
        audit, _ = self._create_manual(self.system_wp.id)
        source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertEqual(
            {q.question_kind for q in source.assertions},
            {AUDIT_QUESTION_KIND_SYSTEM},
        )


class IntegrityGuardNoAutoDeleteTestCase(unittest.TestCase):
    """Obecný guard blokuje nekonzistenci — bez auto-mazání."""

    def setUp(self) -> None:
        _prepare_snapshot_schema()
        self.wp = settings_service.save_workplace(name="Guard WP", active=True)

    def _seed_inconsistent_partial_snapshot(self) -> Audit:
        audit = audit_service.create_audit(
            workplace_id=self.wp.id,
            workplace_name=self.wp.name,
            year=2026,
            started_at=date(2026, 8, 1),
            title="Nekonzistentní partial",
        )
        with get_session() as session:
            row = session.get(Audit, audit.id)
            assert row is not None
            # Markery NULL + existující snaps = inconsistent (ne pristine).
            row.methodology_source = None
            row.methodology_generation = None
            row.questions_frozen_at = None
            session.add(
                AuditQuestionSnapshot(
                    audit_id=audit.id,
                    process_id="p",
                    process_name="P",
                    section_id="s",
                    section_name="S",
                    assertion_id="a1",
                    assertion_text="Orphan snap",
                    verification_type="documentation",
                    severity="normal",
                    question_kind=AUDIT_QUESTION_KIND_OPERATION,
                    display_order=0,
                    is_in_scope=True,
                    created_at=datetime.now(),
                )
            )
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def test_02_startup_does_not_offer_auto_delete(self) -> None:
        upgrade_src = (_REPO / "core" / "database" / "upgrade_guard.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("offer_incomplete_manual_audit_cleanup", upgrade_src)
        self.assertNotIn("Odstranit neúplný testovací audit", upgrade_src)
        self.assertNotIn("incomplete_manual_audit_cleanup", upgrade_src)

    def test_03_04_inconsistent_blocks_with_diagnosis(self) -> None:
        audit = self._seed_inconsistent_partial_snapshot()
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        item = classify_audit_backfill_state(
            audit, snapshot_rows=snaps, control_results=[]
        )
        self.assertEqual(item.status, AUDIT_BACKFILL_STATUS_INCONSISTENT)
        self.assertIn("částečný", item.detail.lower())

        with self.assertRaises(AuditSnapshotBackfillError) as ctx:
            prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        message = str(ctx.exception)
        self.assertIn("nekonzistentní", message.lower())
        self.assertIn(f"id={audit.id}", message)
        self.assertIn("Obnovte zálohu", message)

    def test_05_guard_does_not_delete_or_rewrite(self) -> None:
        audit = self._seed_inconsistent_partial_snapshot()
        before_snaps = 0
        with get_session() as session:
            before_snaps = len(
                list(
                    session.scalars(
                        select(AuditQuestionSnapshot).where(
                            AuditQuestionSnapshot.audit_id == audit.id
                        )
                    )
                )
            )
        with self.assertRaises(AuditSnapshotBackfillError):
            prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)

        still = audit_service.get_by_id(audit.id)
        assert still is not None
        self.assertIsNone(still.methodology_source)
        self.assertIsNone(still.methodology_generation)
        self.assertIsNone(still.questions_frozen_at)
        with get_session() as session:
            after_snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual(len(after_snaps), before_snaps)
        self.assertEqual(after_snaps[0].assertion_text, "Orphan snap")


class ProgramVisitStillV2TestCase(unittest.TestCase):
    def test_12_program_visit_still_v2(self) -> None:
        system_wp = settings_service.save_workplace(name="Sys Prog C", active=True)
        ops_wp = settings_service.save_workplace(name="Ops Prog C", active=True)
        system_audit_workplace_service.set_system_audit_workplace_id(system_wp.id)
        tree = _mixed_tree()
        program = audit_program_service.create_program(
            name="Program U2c",
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
            audit = audit_program_service.create_audit_from_visit(visit.id, started_at=date(2026, 4, 10))
            audit = audit_program_service.prepare_audit_from_visit(audit.id)
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


class LegacyUntouchedTestCase(unittest.TestCase):
    def test_13_legacy_v1_untouched_by_manual_create(self) -> None:
        wp = settings_service.save_workplace(name="Legacy WP C", active=True)
        system = settings_service.save_workplace(name="Sys Legacy C", active=True)
        system_audit_workplace_service.set_system_audit_workplace_id(system.id)

        legacy = audit_service.create_audit(
            workplace_id=wp.id,
            workplace_name=wp.name,
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
        tree = _mixed_tree()
        with patch.object(
            audit_knowledge_service, "get_knowledge_tree", return_value=tree
        ):
            create_manual_audit_with_v2_snapshot(
                fields={
                    "workplace_id": wp.id,
                    "year": 2026,
                    "started_at": date.today(),
                },
            )
        after = audit_service.get_by_id(legacy.id)
        assert after is not None
        self.assertEqual(after.methodology_generation, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1)
        self.assertEqual(after.snapshot_integrity_hash, before_hash)


if __name__ == "__main__":
    unittest.main()
