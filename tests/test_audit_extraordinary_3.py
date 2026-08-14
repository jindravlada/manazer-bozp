"""AUDIT-EXTRAORDINARY-3: typ ověření Dokumentace/Terén a výstupy."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select, text

_TMP = Path(tempfile.mkdtemp(prefix="audit-extraordinary-3-"))
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
    )
    from moduly.audity.sluzby.audit_extraordinary_3_schema_migration import (
        apply_audit_extraordinary_3_schema_ddl,
        needs_audit_extraordinary_3_schema,
        schema_is_present as schema3_present,
    )
    from moduly.audity.sluzby.audit_method_support_snapshot_1_schema_migration import (
        apply_method_support_snapshot_1_schema_ddl,
    )

    apply_audit_extraordinary_schema_ddl(_DB)
    apply_audit_extraordinary_2_schema_ddl(_DB)
    apply_audit_extraordinary_3_schema_ddl(_DB)
    apply_method_support_snapshot_1_schema_ddl(_DB)

    from core.database.session import get_session
    from core.shared.constants import (
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.verification_type import (
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
    )
    from moduly.audity.constants import (
        AUDIT_QUESTION_KIND_EXTRAORDINARY,
        AUDIT_QUESTION_KIND_OPERATION,
        AUDIT_QUESTION_KIND_SYSTEM,
        CONTROL_POINT_SEVERITY_STREDNI,
        CONTROL_POINT_SEVERITY_VYSOKA,
        EXTRAORDINARY_CATEGORY_PROCESS_ID,
        EXTRAORDINARY_CHECKLIST_SECTION_TITLE,
        EXTRAORDINARY_EXPORT_SECTION_TITLE,
        EXTRAORDINARY_INCOMPLETE_VERIFICATION_TYPE_FOR_AUDIT,
        EXTRAORDINARY_TAB_EMPTY_MESSAGE,
        EXTRAORDINARY_VERIFICATION_TYPE_LEGACY_LABEL,
        EXTRAORDINARY_VERIFICATION_TYPE_REQUIRED,
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
        format_verification_type_label,
    )
    from moduly.audity.sluzby.audit_extraordinary_summary_service import (
        build_extraordinary_summary_text,
    )
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode
    from moduly.audity.sluzby.audit_question_kind import interpret_question_kind
    from moduly.audity.sluzby.audit_question_source_service import (
        SnapshotAssertionView,
        build_knowledge_tree_from_snapshot_views,
        filter_knowledge_roots_by_question_kind,
    )
    from moduly.audity.sluzby.audit_terrain_checklist_service import (
        audit_terrain_checklist_service,
    )
    from moduly.audity.sluzby.audit_v2_create_service import (
        create_audit_with_v2_snapshot,
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
        "id": "sec_e3",
        "nazev": "Sekce E3",
        "aktivni": True,
        "auditni_tvrzeni": [
            _question("sys_e3", "Systém E3", kind=AUDIT_QUESTION_KIND_SYSTEM),
            _question("ops_e3", "Provoz E3", kind=AUDIT_QUESTION_KIND_OPERATION),
        ],
        "sekce": [],
    }
    section_node = KnowledgeTreeNode(
        node_type="section",
        node_id=section["id"],
        label=section["nazev"],
        process_id="proc_e3",
        process_label="Proces E3",
        section=section,
        children=(),
    )
    return [
        KnowledgeTreeNode(
            node_type="process",
            node_id="proc_e3",
            label="Proces E3",
            process_id="proc_e3",
            process_label="Proces E3",
            section=None,
            children=(section_node,),
        )
    ]


class Extraordinary3TestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(text("DELETE FROM audit_extraordinary_question_targets"))
            session.execute(text("DELETE FROM audit_extraordinary_questions"))
            session.execute(text("DELETE FROM audit_question_support_snapshots"))
            session.execute(text("DELETE FROM audit_question_snapshots"))
            session.execute(text("DELETE FROM control_results"))
            session.execute(text("DELETE FROM findings"))
            session.execute(text("DELETE FROM audits"))
            session.commit()

        self.system = settings_service.save_workplace(
            name="E3 Systém", active=True, audit_enabled=True
        )
        self.wp_a = settings_service.save_workplace(
            name="E3 Provoz A", active=True, audit_enabled=True
        )
        system_audit_workplace_service.set_system_audit_workplace_id(self.system.id)
        self.tree = _fake_tree()

    def test_01_schema_column_present(self) -> None:
        self.assertTrue(schema3_present(_DB))
        self.assertFalse(needs_audit_extraordinary_3_schema(_DB))

    def test_02_verification_type_required_existing_values(self) -> None:
        with self.assertRaises(AuditExtraordinaryError) as ctx:
            audit_extraordinary_question_service.create_question(
                question_text="Bez typu",
                severity=CONTROL_POINT_SEVERITY_STREDNI,
                workplace_ids=[self.wp_a.id],
            )
        self.assertEqual(str(ctx.exception), EXTRAORDINARY_VERIFICATION_TYPE_REQUIRED)

        q = audit_extraordinary_question_service.create_question(
            question_text="Terénní",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_TERRAIN,
            workplace_ids=[self.wp_a.id],
        )
        self.assertEqual(q.verification_type, VERIFICATION_TYPE_TERRAIN)
        self.assertEqual(
            format_verification_type_label(VERIFICATION_TYPE_DOCUMENTATION),
            "Dokumentace",
        )
        self.assertEqual(
            format_verification_type_label(None),
            EXTRAORDINARY_VERIFICATION_TYPE_LEGACY_LABEL,
        )

    def test_03_legacy_without_type_openable(self) -> None:
        q = audit_extraordinary_question_service.create_question(
            question_text="Legacy",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id],
        )
        with get_session() as session:
            session.execute(
                text(
                    "UPDATE audit_extraordinary_questions "
                    "SET verification_type=NULL WHERE id=:id"
                ),
                {"id": int(q.id)},
            )
            session.commit()
        loaded, _targets = audit_extraordinary_question_service.get_question(int(q.id))
        self.assertIsNone(loaded.verification_type)
        rows = audit_extraordinary_question_service.list_overview_rows()
        row = next(item for item in rows if item.question_id == int(q.id))
        self.assertEqual(
            row.verification_type_label, EXTRAORDINARY_VERIFICATION_TYPE_LEGACY_LABEL
        )

    def test_04_block_new_audit_when_pending_without_type_full_rollback(self) -> None:
        incomplete = audit_extraordinary_question_service.create_question(
            question_text="Neúplný typ",
            severity=CONTROL_POINT_SEVERITY_VYSOKA,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id],
        )
        with get_session() as session:
            session.execute(
                text(
                    "UPDATE audit_extraordinary_questions "
                    "SET verification_type=NULL WHERE id=:id"
                ),
                {"id": int(incomplete.id)},
            )
            session.commit()

        before_audits = 0
        before_snaps = 0
        with get_session() as session:
            before_audits = session.execute(text("SELECT COUNT(*) FROM audits")).scalar()
            before_snaps = session.execute(
                text("SELECT COUNT(*) FROM audit_question_snapshots")
            ).scalar()

        with self.assertRaises(AuditExtraordinaryError) as ctx:
            create_audit_with_v2_snapshot(
                fields={
                    "year": 2026,
                    "started_at": date.today(),
                    "title": "E3 block",
                },
                workplace_id=int(self.wp_a.id),
                planned_process_ids={"proc_e3"},
                knowledge_tree=self.tree,
                ensure_knowledge=False,
            )
        self.assertIn(str(incomplete.id), str(ctx.exception))
        self.assertIn("Neúplný typ", str(ctx.exception))

        with get_session() as session:
            after_audits = session.execute(text("SELECT COUNT(*) FROM audits")).scalar()
            after_snaps = session.execute(
                text("SELECT COUNT(*) FROM audit_question_snapshots")
            ).scalar()
            pending = session.execute(
                text(
                    "SELECT status FROM audit_extraordinary_question_targets "
                    "WHERE question_id=:qid"
                ),
                {"qid": int(incomplete.id)},
            ).scalar()
        self.assertEqual(after_audits, before_audits)
        self.assertEqual(after_snaps, before_snaps)
        self.assertEqual(pending, "pending")

    def test_05_freeze_verification_type_into_snapshot(self) -> None:
        q = audit_extraordinary_question_service.create_question(
            question_text="Zmrazit teren",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_TERRAIN,
            workplace_ids=[self.wp_a.id],
        )
        audit = create_audit_with_v2_snapshot(
            fields={
                "year": 2026,
                "started_at": date.today(),
                "title": "E3 freeze",
            },
            workplace_id=int(self.wp_a.id),
            planned_process_ids={"proc_e3"},
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        with get_session() as session:
            snap = session.scalars(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id
                    == extraordinary_assertion_id(int(q.id)),
                )
            ).one()
            self.assertEqual(snap.verification_type, VERIFICATION_TYPE_TERRAIN)
            self.assertEqual(snap.question_kind, AUDIT_QUESTION_KIND_EXTRAORDINARY)

            # Změna živé definice nesmí ovlivnit snapshot.
            session.execute(
                text(
                    "UPDATE audit_extraordinary_questions "
                    "SET verification_type=:vt WHERE id=:id"
                ),
                {"vt": VERIFICATION_TYPE_DOCUMENTATION, "id": int(q.id)},
            )
            session.commit()

        with get_session() as session:
            snap2 = session.scalars(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id
                    == extraordinary_assertion_id(int(q.id)),
                )
            ).one()
            self.assertEqual(snap2.verification_type, VERIFICATION_TYPE_TERRAIN)

    def test_06_all_types_in_extraordinary_tab_not_in_dok_teren(self) -> None:
        views = [
            SnapshotAssertionView(
                process_id="proc_e3",
                process_name="Proces E3",
                section_id="sec_e3",
                section_name="Sekce",
                assertion_id="ops_e3",
                assertion_text="Provoz",
                verification_type=VERIFICATION_TYPE_TERRAIN,
                severity="stredni",
                question_kind=AUDIT_QUESTION_KIND_OPERATION,
                display_order=1,
            ),
            SnapshotAssertionView(
                process_id=EXTRAORDINARY_CATEGORY_PROCESS_ID,
                process_name="Mimořádná ověření",
                section_id="__extraordinary_section__",
                section_name="Mimořádná ověření",
                assertion_id="eq-1",
                assertion_text="Extra dok",
                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                severity="stredni",
                question_kind=AUDIT_QUESTION_KIND_EXTRAORDINARY,
                display_order=100000,
            ),
            SnapshotAssertionView(
                process_id=EXTRAORDINARY_CATEGORY_PROCESS_ID,
                process_name="Mimořádná ověření",
                section_id="__extraordinary_section__",
                section_name="Mimořádná ověření",
                assertion_id="eq-2",
                assertion_text="Extra teren",
                verification_type=VERIFICATION_TYPE_TERRAIN,
                severity="vysoka",
                question_kind=AUDIT_QUESTION_KIND_EXTRAORDINARY,
                display_order=100001,
            ),
            SnapshotAssertionView(
                process_id=EXTRAORDINARY_CATEGORY_PROCESS_ID,
                process_name="Mimořádná ověření",
                section_id="__extraordinary_section__",
                section_name="Mimořádná ověření",
                assertion_id="eq-3",
                assertion_text="Extra legacy",
                verification_type="",
                severity="stredni",
                question_kind=AUDIT_QUESTION_KIND_EXTRAORDINARY,
                display_order=100002,
            ),
        ]
        roots = build_knowledge_tree_from_snapshot_views(views)
        extraordinary = filter_knowledge_roots_by_question_kind(
            roots, extraordinary_only=True
        )
        standard = filter_knowledge_roots_by_question_kind(
            roots, extraordinary_only=False
        )
        extra_ids: list[str] = []
        for node in extraordinary:
            for child in node.children:
                for raw in child.section.get("auditni_tvrzeni") or []:
                    extra_ids.append(str(raw.get("id")))
                    self.assertEqual(
                        interpret_question_kind(raw.get("question_kind")),
                        AUDIT_QUESTION_KIND_EXTRAORDINARY,
                    )
        self.assertEqual(sorted(extra_ids), ["eq-1", "eq-2", "eq-3"])

        for node in standard:
            for child in node.children:
                for raw in child.section.get("auditni_tvrzeni") or []:
                    self.assertNotEqual(
                        interpret_question_kind(raw.get("question_kind")),
                        AUDIT_QUESTION_KIND_EXTRAORDINARY,
                    )

    def test_07_checklist_only_terrain_extraordinary(self) -> None:
        q_doc = audit_extraordinary_question_service.create_question(
            question_text="Dok checklist",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id],
        )
        q_ter = audit_extraordinary_question_service.create_question(
            question_text="Terén checklist",
            severity=CONTROL_POINT_SEVERITY_VYSOKA,
            verification_type=VERIFICATION_TYPE_TERRAIN,
            workplace_ids=[self.wp_a.id],
        )
        audit = create_audit_with_v2_snapshot(
            fields={
                "year": 2026,
                "started_at": date.today(),
                "title": "E3 checklist",
            },
            workplace_id=int(self.wp_a.id),
            planned_process_ids={"proc_e3"},
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        # Legacy bez typu ve snapshotu (historický řádek) — nesmí do checklistu.
        with get_session() as session:
            session.add(
                AuditQuestionSnapshot(
                    audit_id=int(audit.id),
                    process_id=EXTRAORDINARY_CATEGORY_PROCESS_ID,
                    process_name="Mimořádná ověření",
                    section_id="__extraordinary_section__",
                    section_name="Mimořádná ověření",
                    assertion_id="eq-legacy",
                    assertion_text="Legacy bez typu",
                    verification_type="",
                    severity="stredni",
                    question_kind=AUDIT_QUESTION_KIND_EXTRAORDINARY,
                    display_order=100050,
                    is_in_scope=True,
                    created_at=datetime.now(),
                )
            )
            session.commit()

        content = audit_terrain_checklist_service._checklist_content(int(audit.id))
        plain = content.plain_text()
        self.assertIn(EXTRAORDINARY_CHECKLIST_SECTION_TITLE, plain)
        self.assertIn("Terén checklist", plain)
        self.assertNotIn("Dok checklist", plain)
        self.assertNotIn("Legacy bez typu", plain)
        _ = q_doc
        _ = q_ter

    def test_08_protocol_and_detailed_and_summary(self) -> None:
        q = audit_extraordinary_question_service.create_question(
            question_text="Export mimořádná",
            severity=CONTROL_POINT_SEVERITY_VYSOKA,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.wp_a.id],
        )
        audit = create_audit_with_v2_snapshot(
            fields={
                "year": 2026,
                "started_at": date.today(),
                "title": "E3 export",
            },
            workplace_id=int(self.wp_a.id),
            planned_process_ids={"proc_e3"},
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        assertion_id = extraordinary_assertion_id(int(q.id))
        control_result_service.set_result(
            ENTITY_AUDITY,
            int(audit.id),
            ControlPointContext(
                area_id=EXTRAORDINARY_CATEGORY_PROCESS_ID,
                area_label="Mimořádná ověření",
                section_id="__extraordinary_section__",
                section_label="Mimořádná ověření",
                control_point_id=assertion_id,
                control_point_label="Export mimořádná",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="Poznámka E3",
        )
        finding_service.create(
            entity_type=ENTITY_AUDITY,
            entity_id=int(audit.id),
            finding_type="neshoda",
            description="Zjištění E3",
            source_control_point_id=assertion_id,
            source_control_point_label="Export mimořádná",
        )

        protocol = audit_export_context_service.build(
            audit, config=PROTOCOL_DOCUMENT_CONFIG
        )
        protocol_section = protocol.extraordinary_section_text(detailed=False)
        self.assertIn(EXTRAORDINARY_EXPORT_SECTION_TITLE, protocol_section.plain_text())
        self.assertIn("Export mimořádná", protocol_section.plain_text())
        self.assertIn("Dokumentace", protocol_section.plain_text())

        detailed = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        )
        detailed_section = detailed.extraordinary_section_text(detailed=True)
        detailed_text = detailed_section.plain_text()
        self.assertIn("Zjištění E3", detailed_text)
        self.assertIn("Poznámka E3", detailed_text)

        summary = build_extraordinary_summary_text([audit])
        self.assertIn("Mimořádná ověření", summary)
        self.assertIn("Celkem mimořádných otázek: 1", summary)

        empty_audit = create_audit_with_v2_snapshot(
            fields={
                "year": 2026,
                "started_at": date.today(),
                "title": "E3 empty",
            },
            workplace_id=int(self.system.id),
            planned_process_ids={"proc_e3"},
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        empty_ctx = audit_export_context_service.build(empty_audit)
        self.assertEqual(empty_ctx.extraordinary_section_text().plain_text().strip(), "")
        self.assertEqual(build_extraordinary_summary_text([empty_audit]), "")
        self.assertEqual(
            empty_ctx.placeholder_values()["mimoradne_overeni_text"].plain_text().strip(),
            "",
        )


if __name__ == "__main__":
    unittest.main()
