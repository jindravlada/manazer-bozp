"""AUDIT-METHOD-V2a: question_kind, systémový provoz, atomický snapshot při create."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="audit-method-v2a-"))
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

from sqlalchemy import select  # noqa: E402

from core.database.session import get_session  # noqa: E402
from moduly.audity.constants import (  # noqa: E402
    AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
    AUDIT_METHODOLOGY_GENERATION_V2,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    AUDIT_QUESTION_KIND_LEGACY,
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
    AUDIT_QUESTION_KIND_UNCLASSIFIED,
    DEFAULT_AUDIT_PROGRAM_STANDARDS,
)
from moduly.audity.modely.audit import Audit  # noqa: E402
from moduly.audity.modely.audit_question_snapshot import (  # noqa: E402
    AuditQuestionSnapshot,
)
from moduly.audity.sluzby.audit_knowledge_service import (  # noqa: E402
    KnowledgeTreeNode,
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service  # noqa: E402
from moduly.audity.sluzby.audit_question_kind import (  # noqa: E402
    AuditQuestionKindError,
    interpret_question_kind,
    validate_question_kind,
)
from moduly.audity.sluzby.audit_question_snapshot_service import (  # noqa: E402
    AuditV2SnapshotError,
    audit_question_snapshot_service,
)
from moduly.audity.sluzby.audit_service import audit_service  # noqa: E402
from moduly.audity.sluzby.system_audit_workplace_service import (  # noqa: E402
    SystemAuditWorkplaceError,
    system_audit_workplace_service,
)
from moduly.nastaveni.sluzby.settings_service import settings_service  # noqa: E402


def _section(
    section_id: str,
    name: str,
    questions: list[dict],
) -> dict:
    return {
        "id": section_id,
        "nazev": name,
        "auditni_tvrzeni": questions,
        "sekce": [],
    }


def _fake_tree(process_id: str, process_name: str, section: dict) -> list[KnowledgeTreeNode]:
    section_node = KnowledgeTreeNode(
        node_type="section",
        node_id=section["id"],
        label=section["nazev"],
        process_id=process_id,
        process_label=process_name,
        section=section,
        children=(),
    )
    root = KnowledgeTreeNode(
        node_type="process",
        node_id=process_id,
        label=process_name,
        process_id=process_id,
        process_label=process_name,
        section=None,
        children=(section_node,),
    )
    return [root]


def _question(qid: str, text: str, *, kind: str | None = None, aktivni: bool = True) -> dict:
    item = {
        "id": qid,
        "text": text,
        "aktivni": aktivni,
        "poradi": 10,
        "verification_type": "dokumentace",
        "zavaznost": "stredni",
    }
    if kind is not None:
        item["question_kind"] = kind
    return item


class QuestionKindValidationTestCase(unittest.TestCase):
    def test_missing_kind_is_unclassified(self) -> None:
        self.assertEqual(interpret_question_kind(None), AUDIT_QUESTION_KIND_UNCLASSIFIED)
        self.assertEqual(interpret_question_kind(""), AUDIT_QUESTION_KIND_UNCLASSIFIED)
        self.assertEqual(
            validate_question_kind(None, allow_missing=True),
            AUDIT_QUESTION_KIND_UNCLASSIFIED,
        )

    def test_known_kinds_validate(self) -> None:
        for kind in (
            AUDIT_QUESTION_KIND_SYSTEM,
            AUDIT_QUESTION_KIND_OPERATION,
            AUDIT_QUESTION_KIND_EXTRAORDINARY,
            AUDIT_QUESTION_KIND_UNCLASSIFIED,
            AUDIT_QUESTION_KIND_LEGACY,
        ):
            self.assertEqual(
                validate_question_kind(kind, allow_legacy=True),
                kind,
            )

    def test_live_methodology_rejects_legacy(self) -> None:
        with self.assertRaises(AuditQuestionKindError) as ctx:
            validate_question_kind(AUDIT_QUESTION_KIND_LEGACY, allow_legacy=False)
        self.assertIn("legacy", str(ctx.exception))

    def test_normalize_preserves_kind_without_rewriting_missing(self) -> None:
        with_kind = audit_knowledge_service.normalize_auditni_tvrzeni(
            [_question("q1", "Systémová", kind=AUDIT_QUESTION_KIND_SYSTEM)]
        )
        self.assertEqual(with_kind[0]["question_kind"], AUDIT_QUESTION_KIND_SYSTEM)

        without = audit_knowledge_service.normalize_auditni_tvrzeni(
            [_question("q2", "Bez druhu")]
        )
        self.assertNotIn("question_kind", without[0])


class SystemWorkplaceServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        system_audit_workplace_service.set_system_audit_workplace_id(None)

    def test_save_and_load(self) -> None:
        workplace = settings_service.save_workplace(name="Systém V2a A", active=True)
        saved = system_audit_workplace_service.set_system_audit_workplace_id(workplace.id)
        self.assertEqual(saved, workplace.id)
        self.assertEqual(
            system_audit_workplace_service.get_system_audit_workplace_id(),
            workplace.id,
        )
        loaded = system_audit_workplace_service.get_system_audit_workplace()
        assert loaded is not None
        self.assertEqual(loaded.id, workplace.id)

    def test_missing_workplace_raises(self) -> None:
        with self.assertRaises(SystemAuditWorkplaceError):
            system_audit_workplace_service.set_system_audit_workplace_id(999_999)

        path = system_audit_workplace_service.settings_path()
        path.write_text(
            '{"system_audit_workplace_id": 888888}\n',
            encoding="utf-8",
        )
        with self.assertRaises(SystemAuditWorkplaceError):
            system_audit_workplace_service.require_system_audit_workplace_id()


class V2SnapshotFilterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.system_wp = settings_service.save_workplace(name="Sys filtr", active=True)
        self.other_wp = settings_service.save_workplace(name="Ops filtr", active=True)
        system_audit_workplace_service.set_system_audit_workplace_id(self.system_wp.id)

        section = _section(
            "sec1",
            "Sekce 1",
            [
                _question("sys1", "Systém 1", kind=AUDIT_QUESTION_KIND_SYSTEM),
                _question("ops1", "Provoz 1", kind=AUDIT_QUESTION_KIND_OPERATION),
                _question("ext1", "Mimořádné", kind=AUDIT_QUESTION_KIND_EXTRAORDINARY),
            ],
        )
        self.tree = _fake_tree("proc_a", "Proces A", section)
        self.audit = audit_service.create_audit(
            workplace_id=self.other_wp.id,
            workplace_name=self.other_wp.name,
            year=2026,
            planned_month=4,
        )

    def test_system_workplace_gets_only_system(self) -> None:
        drafts = audit_question_snapshot_service.build_v2_snapshot_for_audit(
            self.audit.id,
            workplace_id=self.system_wp.id,
            system_workplace_id=self.system_wp.id,
            planned_process_ids={"proc_a"},
            ensure=False,
            knowledge_tree=self.tree,
        )
        kinds = {d.question_kind for d in drafts}
        ids = {d.assertion_id for d in drafts}
        self.assertEqual(kinds, {AUDIT_QUESTION_KIND_SYSTEM})
        self.assertEqual(ids, {"sys1"})
        self.assertTrue(all(d.is_in_scope for d in drafts))

    def test_other_workplace_gets_only_operation(self) -> None:
        drafts = audit_question_snapshot_service.build_v2_snapshot_for_audit(
            self.audit.id,
            workplace_id=self.other_wp.id,
            system_workplace_id=self.system_wp.id,
            planned_process_ids={"proc_a"},
            ensure=False,
            knowledge_tree=self.tree,
        )
        kinds = {d.question_kind for d in drafts}
        ids = {d.assertion_id for d in drafts}
        self.assertEqual(kinds, {AUDIT_QUESTION_KIND_OPERATION})
        self.assertEqual(ids, {"ops1"})

    def test_extraordinary_excluded(self) -> None:
        drafts = audit_question_snapshot_service.build_v2_snapshot_for_audit(
            self.audit.id,
            workplace_id=self.other_wp.id,
            system_workplace_id=self.system_wp.id,
            planned_process_ids={"proc_a"},
            ensure=False,
            knowledge_tree=self.tree,
        )
        self.assertNotIn("ext1", {d.assertion_id for d in drafts})

    def test_unclassified_blocks_with_diagnostics(self) -> None:
        section = _section(
            "sec1",
            "Sekce 1",
            [
                _question("ops1", "Provoz 1", kind=AUDIT_QUESTION_KIND_OPERATION),
                _question("unc1", "Nezařazeno"),
            ],
        )
        tree = _fake_tree("proc_a", "Proces A", section)
        with self.assertRaises(AuditV2SnapshotError) as ctx:
            audit_question_snapshot_service.build_v2_snapshot_for_audit(
                self.audit.id,
                workplace_id=self.other_wp.id,
                system_workplace_id=self.system_wp.id,
                planned_process_ids={"proc_a"},
                ensure=False,
                knowledge_tree=tree,
            )
        message = str(ctx.exception)
        self.assertIn("Proces A", message)
        self.assertIn("Sekce 1", message)
        self.assertIn("unc1", message)

    def test_legacy_in_methodology_rejected(self) -> None:
        section = _section(
            "sec_legacy",
            "Sekce L",
            [_question("leg1", "Legacy", kind=AUDIT_QUESTION_KIND_LEGACY)],
        )
        tree = _fake_tree("proc_l", "Proces L", section)
        with self.assertRaises(AuditV2SnapshotError) as ctx:
            audit_question_snapshot_service.build_v2_snapshot_for_audit(
                self.audit.id,
                workplace_id=self.other_wp.id,
                system_workplace_id=self.system_wp.id,
                planned_process_ids={"proc_l"},
                ensure=False,
                knowledge_tree=tree,
            )
        self.assertIn("legacy", str(ctx.exception))


class AtomicV2CreateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.system_wp = settings_service.save_workplace(name="Sys create", active=True)
        self.other_wp = settings_service.save_workplace(name="Ops create", active=True)
        system_audit_workplace_service.set_system_audit_workplace_id(self.system_wp.id)

        section = _section(
            "sec_c",
            "Sekce C",
            [
                _question("sys_c", "Systém C", kind=AUDIT_QUESTION_KIND_SYSTEM),
                _question("ops_c", "Provoz C", kind=AUDIT_QUESTION_KIND_OPERATION),
            ],
        )
        self.tree = _fake_tree("proc_c", "Proces C", section)

        self.program = audit_program_service.create_program(
            name="Program V2a",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            self.program.id,
            workplace_id=self.other_wp.id,
            workplace_name=self.other_wp.name,
            audit_interval_months=6,
        )
        self.visit = audit_program_service.add_visit(
            self.program.id,
            workplace_id=self.other_wp.id,
            planned_year=2026,
            planned_month=5,
            planned_date=date(2026, 5, 10),
        )
        audit_program_service.add_visit_process(
            self.visit.id,
            process_id="proc_c",
            process_name="Proces C",
        )

    def _create(self):
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            return_value=self.tree,
        ) as mocked_tree:
            audit = audit_program_service.create_audit_from_visit(self.visit.id, started_at=date(2026, 4, 10))
            audit = audit_program_service.prepare_audit_from_visit(audit.id)
            return audit, mocked_tree

    def test_new_audit_is_snapshot_v2(self) -> None:
        audit, mocked_tree = self._create()
        self.assertEqual(audit.methodology_source, AUDIT_METHODOLOGY_SOURCE_SNAPSHOT)
        self.assertEqual(audit.methodology_generation, AUDIT_METHODOLOGY_GENERATION_V2)
        self.assertIsNotNone(audit.questions_frozen_at)
        mocked_tree.assert_called_once()
        self.assertTrue(mocked_tree.call_args.kwargs.get("ensure", True))

        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].assertion_id, "ops_c")
        self.assertEqual(snaps[0].question_kind, AUDIT_QUESTION_KIND_OPERATION)
        self.assertTrue(snaps[0].is_in_scope)

        refreshed = audit_program_service.repository.get_visit(self.visit.id)
        assert refreshed is not None
        self.assertEqual(refreshed.audit_id, audit.id)

    def test_system_visit_gets_system_questions(self) -> None:
        audit_program_service.add_workplace(
            self.program.id,
            workplace_id=self.system_wp.id,
            workplace_name=self.system_wp.name,
            audit_interval_months=6,
        )
        visit = audit_program_service.add_visit(
            self.program.id,
            workplace_id=self.system_wp.id,
            planned_year=2026,
            planned_month=6,
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id="proc_c",
            process_name="Proces C",
        )
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            return_value=self.tree,
        ):
            audit = audit_program_service.create_audit_from_visit(visit.id, started_at=date(2026, 4, 10))
            audit = audit_program_service.prepare_audit_from_visit(audit.id)

        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual({s.assertion_id for s in snaps}, {"sys_c"})
        self.assertEqual({s.question_kind for s in snaps}, {AUDIT_QUESTION_KIND_SYSTEM})

    def test_snapshot_error_rolls_back_audit_and_visit(self) -> None:
        bad_section = _section(
            "sec_bad",
            "Sekce Bad",
            [_question("bad1", "Bez druhu")],
        )
        bad_tree = _fake_tree("proc_c", "Proces C", bad_section)
        before_audits = len(audit_service.get_all())

        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            return_value=bad_tree,
        ):
            audit = audit_program_service.create_audit_from_visit(
                self.visit.id, started_at=date(2026, 4, 10)
            )
            with self.assertRaises(AuditV2SnapshotError):
                audit_program_service.prepare_audit_from_visit(audit.id)

        self.assertEqual(len(audit_service.get_all()), before_audits + 1)
        refreshed = audit_program_service.repository.get_visit(self.visit.id)
        assert refreshed is not None
        self.assertEqual(refreshed.audit_id, audit.id)

        with get_session() as session:
            orphan_snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.assertion_id == "bad1"
                    )
                )
            )
        self.assertEqual(orphan_snaps, [])

    def test_json_change_after_create_does_not_affect_snapshot(self) -> None:
        audit, _ = self._create()
        mutated = _section(
            "sec_c",
            "Sekce C",
            [
                _question("ops_c", "Provoz C MUTATED", kind=AUDIT_QUESTION_KIND_OPERATION),
                _question("ops_new", "Nová po zmrazení", kind=AUDIT_QUESTION_KIND_OPERATION),
            ],
        )
        mutated_tree = _fake_tree("proc_c", "Proces C", mutated)
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            return_value=mutated_tree,
        ):
            # Znovu sestavení z živé metodiky by mělo jiné otázky — snapshot DB ne.
            live_drafts = audit_question_snapshot_service.build_v2_snapshot_for_audit(
                audit.id,
                workplace_id=self.other_wp.id,
                system_workplace_id=self.system_wp.id,
                planned_process_ids={"proc_c"},
                ensure=False,
                knowledge_tree=mutated_tree,
            )
        self.assertEqual({d.assertion_id for d in live_drafts}, {"ops_c", "ops_new"})

        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual({s.assertion_id for s in snaps}, {"ops_c"})
        self.assertEqual(snaps[0].assertion_text, "Provoz C")

    def test_system_workplace_change_does_not_affect_snapshot(self) -> None:
        audit, _ = self._create()
        new_system = settings_service.save_workplace(name="Nový systém", active=True)
        system_audit_workplace_service.set_system_audit_workplace_id(new_system.id)

        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual({s.assertion_id for s in snaps}, {"ops_c"})
        self.assertEqual({s.question_kind for s in snaps}, {AUDIT_QUESTION_KIND_OPERATION})

    def test_legacy_audit_untouched(self) -> None:
        legacy = audit_service.create_audit(
            workplace_id=self.other_wp.id,
            workplace_name=self.other_wp.name,
            year=2025,
            planned_month=1,
        )
        with get_session() as session:
            db = session.get(Audit, legacy.id)
            assert db is not None
            db.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
            db.methodology_generation = AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
            session.add(
                AuditQuestionSnapshot(
                    audit_id=legacy.id,
                    process_id="p",
                    process_name="P",
                    section_id="s",
                    section_name="S",
                    assertion_id="legacy_q",
                    assertion_text="Legacy text",
                    verification_type="dokumentace",
                    severity="stredni",
                    question_kind=AUDIT_QUESTION_KIND_LEGACY,
                    display_order=1,
                    is_in_scope=True,
                )
            )
            session.commit()

        self._create()

        reloaded = audit_service.get_by_id(legacy.id)
        assert reloaded is not None
        self.assertEqual(
            reloaded.methodology_generation, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
        )
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == legacy.id
                    )
                )
            )
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].question_kind, AUDIT_QUESTION_KIND_LEGACY)

    def test_create_does_not_call_methodology_repeatedly(self) -> None:
        ensure_calls = {"n": 0}
        original_ensure = audit_knowledge_service.ensure_catalogs

        def counting_ensure():
            ensure_calls["n"] += 1
            return original_ensure()

        tree_calls = {"n": 0}
        original_tree = audit_knowledge_service.get_knowledge_tree

        def counting_tree(*, ensure: bool = True):
            tree_calls["n"] += 1
            if ensure:
                counting_ensure()
            return self.tree

        with patch.object(
            audit_knowledge_service, "ensure_catalogs", side_effect=counting_ensure
        ), patch.object(
            audit_knowledge_service, "get_knowledge_tree", side_effect=counting_tree
        ):
            audit = audit_program_service.create_audit_from_visit(self.visit.id, started_at=date(2026, 4, 10))
            self.assertEqual(tree_calls["n"], 0)
            audit_program_service.prepare_audit_from_visit(audit.id)

        self.assertEqual(tree_calls["n"], 1)
        self.assertLessEqual(ensure_calls["n"], 2)


if __name__ == "__main__":
    unittest.main()
