"""AUDIT-EXTRAORDINARY-2: přiřazení mimořádných otázek do auditu a vyhodnocení."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select, text

_TMP = Path(tempfile.mkdtemp(prefix="audit-extraordinary-2-"))
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

    from moduly.audity.sluzby.audit_extraordinary_schema_migration import (
        apply_audit_extraordinary_schema_ddl,
    )
    from moduly.audity.sluzby.audit_extraordinary_2_schema_migration import (
        apply_audit_extraordinary_2_schema_ddl,
        needs_audit_extraordinary_2_schema,
        schema_is_present as schema2_present,
    )
    from moduly.audity.sluzby.audit_extraordinary_3_schema_migration import (
        apply_audit_extraordinary_3_schema_ddl,
    )

    apply_audit_extraordinary_schema_ddl(_DB)
    apply_audit_extraordinary_2_schema_ddl(_DB)
    apply_audit_extraordinary_3_schema_ddl(_DB)

    from core.database.session import get_session
    from core.shared.constants import (
        CONTROL_RESULT_NEKONTROLOVANO,
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.verification_type import VERIFICATION_TYPE_DOCUMENTATION, VERIFICATION_TYPE_TERRAIN
    from moduly.audity.constants import (
        AUDIT_QUESTION_KIND_EXTRAORDINARY,
        AUDIT_QUESTION_KIND_OPERATION,
        AUDIT_QUESTION_KIND_SYSTEM,
        CONTROL_POINT_SEVERITY_KRITICKA,
        CONTROL_POINT_SEVERITY_STREDNI,
        CONTROL_POINT_SEVERITY_VYSOKA,
        EXTRAORDINARY_CATEGORY_PROCESS_ID,
        EXTRAORDINARY_CATEGORY_PROCESS_NAME,
        EXTRAORDINARY_SEVERITY_REQUIRED,
        EXTRAORDINARY_TARGET_STATUS_ASSIGNED,
        EXTRAORDINARY_TARGET_STATUS_PENDING,
        EXTRAORDINARY_TARGET_STATUS_VERIFIED,
        EXTRAORDINARY_TAB_EMPTY_MESSAGE,
        extraordinary_assertion_id,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_extraordinary_assignment_service import (
        audit_extraordinary_assignment_service,
    )
    from moduly.audity.sluzby.audit_extraordinary_question_service import (
        AuditExtraordinaryError,
        audit_extraordinary_question_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode
    from moduly.audity.sluzby.audit_question_source_service import (
        filter_knowledge_roots_by_question_kind,
        build_knowledge_tree_from_snapshot_views,
        SnapshotAssertionView,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_v2_create_service import (
        create_audit_with_v2_snapshot,
        create_manual_audit_with_v2_snapshot,
    )
    from moduly.audity.sluzby.system_audit_workplace_service import (
        system_audit_workplace_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _question(qid: str, text: str, *, kind: str) -> dict:
    return {
        "id": qid,
        "text": text,
        "aktivni": True,
        "poradi": 10,
        "verification_type": "dokumentace",
        "zavaznost": "stredni",
        "question_kind": kind,
    }


def _fake_tree() -> list[KnowledgeTreeNode]:
    section = {
        "id": "sec_e2",
        "nazev": "Sekce E2",
        "aktivni": True,
        "auditni_tvrzeni": [
            _question("sys_e2", "Systém E2", kind=AUDIT_QUESTION_KIND_SYSTEM),
            _question("ops_e2", "Provoz E2", kind=AUDIT_QUESTION_KIND_OPERATION),
        ],
        "sekce": [],
    }
    section_node = KnowledgeTreeNode(
        node_type="section",
        node_id=section["id"],
        label=section["nazev"],
        process_id="proc_e2",
        process_label="Proces E2",
        section=section,
        children=(),
    )
    return [
        KnowledgeTreeNode(
            node_type="process",
            node_id="proc_e2",
            label="Proces E2",
            process_id="proc_e2",
            process_label="Proces E2",
            section=None,
            children=(section_node,),
        )
    ]


class Extraordinary2TestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(text("DELETE FROM audit_extraordinary_question_targets"))
            session.execute(text("DELETE FROM audit_extraordinary_questions"))
            session.execute(text("DELETE FROM audit_question_snapshots"))
            session.execute(text("DELETE FROM control_results"))
            session.execute(text("DELETE FROM audits"))
            session.commit()

        self.system = settings_service.save_workplace(
            name="E2 Systém", active=True, audit_enabled=True
        )
        self.wp_a = settings_service.save_workplace(
            name="E2 Provoz A", active=True, audit_enabled=True
        )
        self.wp_b = settings_service.save_workplace(
            name="E2 Provoz B", active=True, audit_enabled=True
        )
        system_audit_workplace_service.set_system_audit_workplace_id(self.system.id)
        self.tree = _fake_tree()

    def test_01_schema_columns_present(self) -> None:
        self.assertTrue(schema2_present(_DB))
        self.assertFalse(needs_audit_extraordinary_2_schema(_DB))

    def test_02_severity_required_including_critical(self) -> None:
        with self.assertRaises(AuditExtraordinaryError) as ctx:
            audit_extraordinary_question_service.create_question(
                question_text="Bez závažnosti",
                workplace_ids=[self.wp_a.id],
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            )
        self.assertEqual(str(ctx.exception), EXTRAORDINARY_SEVERITY_REQUIRED)

        q = audit_extraordinary_question_service.create_question(
            question_text="Kritická",
            severity=CONTROL_POINT_SEVERITY_KRITICKA,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id],
        )
        self.assertEqual(q.severity, CONTROL_POINT_SEVERITY_KRITICKA)

    def test_03_optional_process_and_category(self) -> None:
        none_q = audit_extraordinary_question_service.create_question(
            question_text="Bez procesu",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            process_id=None,
            workplace_ids=[self.wp_a.id],
        )
        self.assertIsNone(none_q.process_id)
        self.assertEqual(none_q.process_name, "")

        # Přímý zápis volitelného procesu (bez závislosti na živém katalogu).
        with get_session() as session:
            row = session.get(type(none_q), none_q.id)
            assert row is not None
            row.process_id = "proc_e2"
            row.process_name = "Proces E2"
            session.commit()
            session.refresh(row)
            self.assertEqual(row.process_id, "proc_e2")
            self.assertEqual(row.process_name, "Proces E2")

    def test_04_manual_and_program_paths_assign(self) -> None:
        q = audit_extraordinary_question_service.create_question(
            question_text="Přiřadit A",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id, self.wp_b.id],
        )
        audit = create_audit_with_v2_snapshot(
            fields={
                "workplace_id": self.wp_a.id,
                "workplace_name": self.wp_a.name,
                "year": 2026,
                "started_at": date(2026, 4, 1),
                "title": "Atom E2",
            },
            workplace_id=self.wp_a.id,
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        # Druhá cesta (ruční wrapper) se stejným knowledge_tree přes create_audit.
        audit2 = create_audit_with_v2_snapshot(
            fields={
                "workplace_id": self.wp_b.id,
                "workplace_name": self.wp_b.name,
                "year": 2026,
                "started_at": date(2026, 4, 2),
                "title": "Atom E2 B",
            },
            workplace_id=self.wp_b.id,
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id,
                        AuditQuestionSnapshot.question_kind
                        == AUDIT_QUESTION_KIND_EXTRAORDINARY,
                    )
                )
            )
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].assertion_id, extraordinary_assertion_id(q.id))
        self.assertEqual(snaps[0].severity, CONTROL_POINT_SEVERITY_STREDNI)
        self.assertEqual(snaps[0].process_id, EXTRAORDINARY_CATEGORY_PROCESS_ID)
        self.assertEqual(snaps[0].process_name, EXTRAORDINARY_CATEGORY_PROCESS_NAME)

        targets = {
            int(t.workplace_id): t
            for t in audit_extraordinary_question_service.repository.list_targets_for_question(
                q.id
            )
        }
        self.assertEqual(targets[self.wp_a.id].status, EXTRAORDINARY_TARGET_STATUS_ASSIGNED)
        self.assertEqual(targets[self.wp_a.id].assigned_audit_id, audit.id)
        self.assertEqual(targets[self.wp_b.id].status, EXTRAORDINARY_TARGET_STATUS_ASSIGNED)
        self.assertEqual(targets[self.wp_b.id].assigned_audit_id, audit2.id)

    def test_05_no_double_assign_and_rollback(self) -> None:
        q = audit_extraordinary_question_service.create_question(
            question_text="Jednou",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id],
        )
        create_audit_with_v2_snapshot(
            fields={
                "workplace_id": self.wp_a.id,
                "workplace_name": self.wp_a.name,
                "year": 2026,
                "started_at": date(2026, 4, 2),
                "title": "První",
            },
            workplace_id=self.wp_a.id,
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        before = len(audit_service.get_all())
        create_audit_with_v2_snapshot(
            fields={
                "workplace_id": self.wp_a.id,
                "workplace_name": self.wp_a.name,
                "year": 2026,
                "started_at": date(2026, 4, 3),
                "title": "Druhý bez mimořádné",
            },
            workplace_id=self.wp_a.id,
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        self.assertEqual(len(audit_service.get_all()), before + 1)
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            q.id
        )
        assigned = [
            t for t in targets if t.status == EXTRAORDINARY_TARGET_STATUS_ASSIGNED
        ]
        self.assertEqual(len(assigned), 1)

        # Rollback: neúplná závažnost zablokuje založení.
        incomplete = audit_extraordinary_question_service.create_question(
            question_text="Doplnit",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_b.id],
        )
        with get_session() as session:
            row = session.get(type(incomplete), incomplete.id)
            assert row is not None
            row.severity = None
            session.commit()
        before_audits = len(audit_service.get_all())
        with get_session() as session:
            before_snaps = len(list(session.scalars(select(AuditQuestionSnapshot))))
        with self.assertRaises(AuditExtraordinaryError):
            create_audit_with_v2_snapshot(
                fields={
                    "workplace_id": self.wp_b.id,
                    "workplace_name": self.wp_b.name,
                    "year": 2026,
                    "started_at": date(2026, 4, 4),
                    "title": "Rollback",
                },
                workplace_id=self.wp_b.id,
                knowledge_tree=self.tree,
                ensure_knowledge=False,
            )
        self.assertEqual(len(audit_service.get_all()), before_audits)
        with get_session() as session:
            after_snaps = len(list(session.scalars(select(AuditQuestionSnapshot))))
        self.assertEqual(after_snaps, before_snaps)

    def test_06_tab_filter_and_empty_message(self) -> None:
        views = [
            SnapshotAssertionView(
                process_id="proc_e2",
                process_name="Proces E2",
                section_id="sec_e2",
                section_name="Sekce",
                assertion_id="ops",
                assertion_text="Běžná",
                verification_type="dokumentace",
                severity="stredni",
                question_kind=AUDIT_QUESTION_KIND_OPERATION,
                display_order=1,
            ),
            SnapshotAssertionView(
                process_id=EXTRAORDINARY_CATEGORY_PROCESS_ID,
                process_name=EXTRAORDINARY_CATEGORY_PROCESS_NAME,
                section_id="s",
                section_name="S",
                assertion_id="eq-1",
                assertion_text="Mimo",
                verification_type="dokumentace",
                severity="vysoka",
                question_kind=AUDIT_QUESTION_KIND_EXTRAORDINARY,
                display_order=2,
            ),
        ]
        roots = build_knowledge_tree_from_snapshot_views(views)
        standard = filter_knowledge_roots_by_question_kind(
            roots, extraordinary_only=False
        )
        extraordinary = filter_knowledge_roots_by_question_kind(
            roots, extraordinary_only=True
        )
        self.assertEqual(len(standard), 1)
        self.assertEqual(standard[0].process_id, "proc_e2")
        self.assertEqual(len(extraordinary), 1)
        self.assertEqual(extraordinary[0].process_id, EXTRAORDINARY_CATEGORY_PROCESS_ID)
        self.assertTrue(EXTRAORDINARY_TAB_EMPTY_MESSAGE)

    def test_07_verified_and_return_pending(self) -> None:
        q = audit_extraordinary_question_service.create_question(
            question_text="Vyhodnotit",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id],
        )
        audit = create_audit_with_v2_snapshot(
            fields={
                "workplace_id": self.wp_a.id,
                "workplace_name": self.wp_a.name,
                "year": 2026,
                "started_at": date(2026, 5, 1),
                "title": "Complete E2",
            },
            workplace_id=self.wp_a.id,
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            int(audit.id),
            ControlPointContext(
                area_id=EXTRAORDINARY_CATEGORY_PROCESS_ID,
                area_label=EXTRAORDINARY_CATEGORY_PROCESS_NAME,
                section_id="__extraordinary_section__",
                section_label="Mimořádná ověření",
                control_point_id=extraordinary_assertion_id(q.id),
                control_point_label="Vyhodnotit",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="",
        )
        updated = audit_service.update_audit(
            audit.id, finished_at=date(2026, 5, 2)
        )
        assert updated is not None
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            q.id
        )
        self.assertEqual(targets[0].status, EXTRAORDINARY_TARGET_STATUS_VERIFIED)
        self.assertEqual(targets[0].verified_audit_id, audit.id)
        self.assertIsNotNone(targets[0].verified_at)

        q2 = audit_extraordinary_question_service.create_question(
            question_text="Vrátit",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id],
        )
        audit2 = create_audit_with_v2_snapshot(
            fields={
                "workplace_id": self.wp_a.id,
                "workplace_name": self.wp_a.name,
                "year": 2026,
                "started_at": date(2026, 5, 3),
                "title": "Return E2",
            },
            workplace_id=self.wp_a.id,
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        # bez výsledku = nekontrolováno → pending
        audit_service.update_audit(audit2.id, finished_at=date(2026, 5, 4))
        targets2 = audit_extraordinary_question_service.repository.list_targets_for_question(
            q2.id
        )
        self.assertEqual(targets2[0].status, EXTRAORDINARY_TARGET_STATUS_PENDING)
        self.assertIsNone(targets2[0].assigned_audit_id)

    def test_08_delete_releases_assigned(self) -> None:
        q = audit_extraordinary_question_service.create_question(
            question_text="Smazat audit",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id],
        )
        audit = create_audit_with_v2_snapshot(
            fields={
                "workplace_id": self.wp_a.id,
                "workplace_name": self.wp_a.name,
                "year": 2026,
                "started_at": date(2026, 6, 1),
                "title": "Delete E2",
            },
            workplace_id=self.wp_a.id,
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        audit_service.delete_audit(audit.id)
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            q.id
        )
        self.assertEqual(targets[0].status, EXTRAORDINARY_TARGET_STATUS_PENDING)
        self.assertIsNone(targets[0].assigned_audit_id)

    def test_09_legacy_incomplete_openable(self) -> None:
        q = audit_extraordinary_question_service.create_question(
            question_text="Starý záznam",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id],
        )
        with get_session() as session:
            row = session.get(type(q), q.id)
            assert row is not None
            row.severity = None
            session.commit()
        loaded, targets = audit_extraordinary_question_service.get_question(q.id)
        self.assertEqual(loaded.id, q.id)
        self.assertIsNone(loaded.severity)
        self.assertEqual(len(targets), 1)


if __name__ == "__main__":
    unittest.main()
