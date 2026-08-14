"""AUDIT-SNAPSHOT-1b: čtení starých auditů ze snapshotu."""

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

_HOME = Path(tempfile.mkdtemp(prefix="audit-snapshot-1b-"))
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

from core.shared.constants import (  # noqa: E402
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
    AUDIT_METHODOLOGY_SOURCE_LIVE,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    AUDIT_QUESTION_KIND_LEGACY,
)
from moduly.audity.modely.audit import Audit  # noqa: E402
from moduly.audity.modely.audit_question_snapshot import (  # noqa: E402
    AuditQuestionSnapshot,
)
from moduly.audity.sluzby.audit_deferred_edits import AuditDeferredEdits  # noqa: E402
from moduly.audity.sluzby.audit_export_context_service import (  # noqa: E402
    DETAILED_REPORT_DOCUMENT_CONFIG,
    PROTOCOL_DOCUMENT_CONFIG,
    AuditExportContext,
)
from moduly.audity.sluzby.audit_knowledge_service import (  # noqa: E402
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_question_source_service import (  # noqa: E402
    AuditQuestionSourceError,
    audit_question_source_service,
    build_knowledge_tree_from_snapshot_views,
)
from moduly.audity.sluzby.audit_service import audit_service  # noqa: E402
from moduly.audity.sluzby.audit_snapshot_backfill_service import (  # noqa: E402
    prepare_audit_snapshot_backfill,
)
from moduly.audity.sluzby.audit_snapshot_schema_migration import (  # noqa: E402
    prepare_audit_snapshot_schema,
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


def _fingerprint_core() -> tuple:
    conn = sqlite3.connect(str(_DB))
    try:
        snaps = conn.execute(
            "SELECT audit_id, process_id, section_id, assertion_id, assertion_text, "
            "verification_type, display_order FROM audit_question_snapshots "
            "ORDER BY id"
        ).fetchall()
        audits = conn.execute(
            "SELECT id, methodology_source, methodology_generation, "
            "questions_frozen_at FROM audits ORDER BY id"
        ).fetchall()
        crs = conn.execute(
            "SELECT id, result, note, photo_path, source_control_point_label "
            "FROM control_results ORDER BY id"
        ).fetchall()
        return (snaps, audits, crs)
    finally:
        conn.close()


class AuditSnapshot1bTestCase(unittest.TestCase):
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
        for leftover in list(audit_service.get_all()):
            audit_service.delete_audit(leftover.id)
        # Vyčisti control_results osiřelé po mazání.
        conn = sqlite3.connect(str(_DB))
        try:
            conn.execute("DELETE FROM control_results WHERE entity_type = ?", (ENTITY_AUDITY,))
            conn.execute("DELETE FROM audit_verification_overrides")
            conn.commit()
        finally:
            conn.close()

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
                        str(q.get("verification_type") or VERIFICATION_TYPE_DOCUMENTATION),
                    )
        self.fail(f"Žádné tvrzení v procesu {process_id}")

    def _seed_snapshot_audit(
        self,
        *,
        title: str = "Snap",
        frozen_text: str = "ZMRAZENÝ TEXT OTÁZKY",
        verification_type: str = VERIFICATION_TYPE_DOCUMENTATION,
        with_result: bool = True,
        include_orphan: bool = False,
        include_unevaluated: bool = True,
    ):
        info = self._first_assertion(self.processes[0].id)
        audit = audit_service.create_audit(title=title)
        if with_result:
            control_result_service.set_result(
                ENTITY_AUDITY,
                audit.id,
                ControlPointContext(
                    area_id=info[0],
                    area_label=info[1],
                    section_id=info[2],
                    section_label=info[3],
                    control_point_id=info[4],
                    control_point_label=frozen_text,
                ),
                result=CONTROL_RESULT_VYHOVUJE,
                note="n",
            )
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)

        with get_session() as session:
            # Přepiš text ve snapshotu na jednoznačný frozen text.
            snap = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id == info[4],
                    AuditQuestionSnapshot.process_id == info[0],
                    AuditQuestionSnapshot.section_id == info[2],
                )
            )
            if snap is not None:
                snap.assertion_text = frozen_text
                snap.verification_type = verification_type
            if include_orphan:
                session.add(
                    AuditQuestionSnapshot(
                        audit_id=audit.id,
                        process_id="orphan_p",
                        process_name="Orphan proces",
                        section_id="orphan_s",
                        section_name="Orphan sekce",
                        assertion_id="orphan_q",
                        assertion_text="ORPHAN ZE SNAPSHOTU",
                        verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                        severity="stredni",
                        question_kind=AUDIT_QUESTION_KIND_LEGACY,
                        display_order=9999,
                        is_in_scope=False,
                        created_at=datetime.now(),
                    )
                )
            if not include_unevaluated and snap is not None:
                for row in list(
                    session.scalars(
                        select(AuditQuestionSnapshot).where(
                            AuditQuestionSnapshot.audit_id == audit.id
                        )
                    )
                ):
                    keep = row.assertion_id == info[4] or (
                        include_orphan and row.assertion_id == "orphan_q"
                    )
                    if not keep:
                        session.delete(row)
            session.commit()

        if include_orphan:
            control_result_service.set_result(
                ENTITY_AUDITY,
                audit.id,
                ControlPointContext(
                    area_id="orphan_p",
                    area_label="Orphan proces",
                    section_id="orphan_s",
                    section_label="Orphan sekce",
                    control_point_id="orphan_q",
                    control_point_label="ORPHAN ZE SNAPSHOTU",
                ),
                result=CONTROL_RESULT_VYHOVUJE,
            )

        return audit_service.get_by_id(audit.id), info, frozen_text

    def test_snapshot_shows_frozen_text(self) -> None:
        audit, info, frozen = self._seed_snapshot_audit()
        source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertTrue(source.is_snapshot)
        texts = {a.assertion_text for a in source.assertions}
        self.assertIn(frozen, texts)
        matched = [
            a
            for a in source.assertions
            if a.assertion_id == info[4] and a.process_id == info[0]
        ]
        self.assertEqual(matched[0].assertion_text, frozen)

    def test_json_text_change_does_not_affect_snapshot(self) -> None:
        audit, info, frozen = self._seed_snapshot_audit(frozen_text="ORIG SNAP")
        with patch.object(
            audit_knowledge_service,
            "get_audit_questions",
            return_value=[
                {
                    "id": info[4],
                    "text": "NOVÝ TEXT Z JSON",
                    "nazev": "NOVÝ TEXT Z JSON",
                    "aktivni": True,
                    "verification_type": VERIFICATION_TYPE_DOCUMENTATION,
                    "zavaznost": "stredni",
                    "poradi": 10,
                }
            ],
        ):
            source = audit_question_source_service.resolve_for_audit(audit.id)
        matched = [
            a
            for a in source.assertions
            if a.assertion_id == info[4] and a.process_id == info[0]
        ]
        self.assertEqual(matched[0].assertion_text, "ORIG SNAP")

    def test_json_removal_does_not_affect_snapshot(self) -> None:
        audit, info, frozen = self._seed_snapshot_audit(frozen_text="ZUSTANE")
        with patch.object(audit_knowledge_service, "get_audit_questions", return_value=[]):
            source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertTrue(any(a.assertion_text == "ZUSTANE" for a in source.assertions))
        self.assertGreater(len(source.assertions), 0)

    def test_new_json_question_not_in_snapshot_audit(self) -> None:
        audit, _info, _frozen = self._seed_snapshot_audit(
            include_unevaluated=False, with_result=True
        )
        source = audit_question_source_service.resolve_for_audit(audit.id)
        ids = {a.assertion_id for a in source.assertions}
        self.assertNotIn("brand_new_json_q", ids)
        # Simulace živé metodiky s novou otázkou — snapshot ji nepřidá.
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            side_effect=AssertionError("snapshot nesmí volat get_knowledge_tree"),
        ):
            again = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertEqual(
            {a.assertion_id for a in again.assertions},
            ids,
        )

    def test_unevaluated_snapshot_question_remains(self) -> None:
        audit = audit_service.create_audit(title="Uneval")
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertGreater(len(source.assertions), 0)
        self.assertEqual(
            len(control_result_service.get_for_entity(ENTITY_AUDITY, audit.id)), 0
        )

    def test_orphan_with_result_remains_hidden(self) -> None:
        audit, _info, _f = self._seed_snapshot_audit(
            include_orphan=True, include_unevaluated=False
        )
        source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertFalse(any(a.assertion_id == "orphan_q" for a in source.assertions))
        with get_session() as session:
            orphan = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id == "orphan_q",
                )
            )
        self.assertIsNotNone(orphan)
        self.assertFalse(orphan.is_in_scope)
        crs = control_result_service.get_for_entity(ENTITY_AUDITY, audit.id)
        self.assertTrue(any(c.source_control_point_id == "orphan_q" for c in crs))

    def test_documentation_terrain_from_snapshot(self) -> None:
        audit, info, _f = self._seed_snapshot_audit(
            verification_type=VERIFICATION_TYPE_TERRAIN,
            include_unevaluated=False,
        )
        teren = audit_verification_service.list_assertions(
            audit.id, verification_type=VERIFICATION_TYPE_TERRAIN
        )
        dok = audit_verification_service.list_assertions(
            audit.id, verification_type=VERIFICATION_TYPE_DOCUMENTATION
        )
        self.assertTrue(any(r.control_point_id == info[4] for r in teren))
        self.assertFalse(any(r.control_point_id == info[4] for r in dok))

    def test_override_has_priority(self) -> None:
        audit, info, _f = self._seed_snapshot_audit(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            include_unevaluated=False,
        )
        audit_verification_service.set_override(
            audit.id,
            area_id=info[0],
            section_id=info[2],
            control_point_id=info[4],
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        teren = audit_verification_service.list_assertions(
            audit.id, verification_type=VERIFICATION_TYPE_TERRAIN
        )
        self.assertTrue(any(r.control_point_id == info[4] for r in teren))

    def test_discard_override_via_deferred(self) -> None:
        audit, info, _f = self._seed_snapshot_audit(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            include_unevaluated=False,
        )
        deferred = AuditDeferredEdits()
        deferred.stage_verification_override(
            audit.id,
            area_id=info[0],
            section_id=info[2],
            control_point_id=info[4],
            verification_type=VERIFICATION_TYPE_TERRAIN,
            methodology_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        self.assertTrue(deferred.has_changes())
        deferred.clear()
        self.assertFalse(deferred.has_changes())
        mapping = audit_verification_service.overrides_map(audit.id)
        self.assertNotIn((info[0], info[2], info[4]), mapping)

    def test_save_result_uses_snapshot_label(self) -> None:
        audit, info, frozen = self._seed_snapshot_audit(frozen_text="LABEL ZE SNAP")
        source = audit_question_source_service.resolve_for_audit(audit.id)
        text = audit_question_source_service.assertion_text(
            source,
            process_id=info[0],
            section_id=info[2],
            assertion_id=info[4],
            fallback="FALLBACK",
        )
        self.assertEqual(text, "LABEL ZE SNAP")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=info[0],
                area_label=info[1],
                section_id=info[2],
                section_label=info[3],
                control_point_id=info[4],
                control_point_label=text,
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        cr = control_result_service.get_for_entity(ENTITY_AUDITY, audit.id)[0]
        self.assertEqual(cr.source_control_point_label, "LABEL ZE SNAP")

    def test_opening_snapshot_audit_writes_nothing(self) -> None:
        audit, _i, _f = self._seed_snapshot_audit()
        before = _fingerprint_core()
        from moduly.audity.ui.audit_dialog import AuditDialog

        dialog = AuditDialog(audit=audit)
        try:
            after = _fingerprint_core()
            self.assertEqual(after, before)
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_snapshot_does_not_call_live_methodology(self) -> None:
        audit, _i, _f = self._seed_snapshot_audit()
        with (
            patch.object(
                audit_knowledge_service,
                "ensure_catalogs",
                side_effect=AssertionError("ensure_catalogs"),
            ),
            patch.object(
                audit_knowledge_service,
                "get_knowledge_tree",
                side_effect=AssertionError("get_knowledge_tree"),
            ),
        ):
            source = audit_question_source_service.resolve_for_audit(audit.id)
            self.assertTrue(source.is_snapshot)
            from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget

            widget = AuditProcessesWidget()
            widget.set_audit_id(audit.id)
            widget.set_question_source(source)
            self.assertGreater(widget.knowledge_tree.topLevelItemCount(), 0)
            widget.deleteLater()

    def test_live_audit_still_uses_json(self) -> None:
        audit = audit_service.create_audit(title="Live")
        with get_session() as session:
            db = session.get(Audit, audit.id)
            db.methodology_source = AUDIT_METHODOLOGY_SOURCE_LIVE
            session.commit()
        source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertFalse(source.is_snapshot)
        self.assertEqual(source.mode, "live")

    def test_empty_valid_snapshot_no_json_fallback(self) -> None:
        audit = audit_service.create_audit(title="Empty snap")
        with get_session() as session:
            db = session.get(Audit, audit.id)
            db.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
            db.methodology_generation = AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
            db.questions_frozen_at = datetime.now()
            session.commit()
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            side_effect=AssertionError("no live tree"),
        ):
            source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertTrue(source.is_snapshot)
        self.assertEqual(source.assertions, ())
        self.assertEqual(source.roots, ())

    def test_inconsistent_snapshot_raises(self) -> None:
        audit, info, _f = self._seed_snapshot_audit(include_unevaluated=False)
        with get_session() as session:
            for row in list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            ):
                session.delete(row)
            session.commit()
        with self.assertRaises(AuditQuestionSourceError):
            audit_question_source_service.resolve_for_audit(audit.id)

    def test_protocol_uses_snapshot_text_and_excludes_orphan(self) -> None:
        audit, info, frozen = self._seed_snapshot_audit(
            frozen_text="PROTOKOL SNAP TEXT",
            include_orphan=True,
            include_unevaluated=False,
        )
        ctx = AuditExportContext(audit=audit, config=PROTOCOL_DOCUMENT_CONFIG)
        appendix = ctx.summary_appendix_assertions().plain_text()
        self.assertIn("PROTOKOL SNAP TEXT", appendix)
        self.assertNotIn("ORPHAN ZE SNAPSHOTU", appendix)
        self.assertNotIn("brand_new_from_json", appendix)
        # Orphan zůstává v DB.
        with get_session() as session:
            orphan = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id,
                    AuditQuestionSnapshot.assertion_id == "orphan_q",
                )
            )
        self.assertIsNotNone(orphan)
        self.assertFalse(orphan.is_in_scope)

    def test_new_json_question_not_in_old_export(self) -> None:
        audit, _i, frozen = self._seed_snapshot_audit(
            frozen_text="ONLY SNAP",
            include_unevaluated=False,
        )
        ctx = AuditExportContext(audit=audit, config=PROTOCOL_DOCUMENT_CONFIG)
        text = ctx.summary_appendix_assertions().plain_text()
        self.assertIn("ONLY SNAP", text)
        live_ids = set()
        for root in audit_knowledge_service.get_knowledge_tree(ensure=False):
            for node in root.children:
                for q in audit_knowledge_service.get_audit_questions(node.section or {}):
                    live_ids.add(str(q.get("id")))
        # Export obsahuje jen vyhodnocené snapshotované výsledky, ne celou živou sadu.
        self.assertNotIn("neexistujici_nova_otazka", text)

    def test_detailed_report_and_terrain_checklist_use_snapshot(self) -> None:
        audit, info, frozen = self._seed_snapshot_audit(
            frozen_text="DETAILED SNAP",
            verification_type=VERIFICATION_TYPE_TERRAIN,
            include_unevaluated=False,
        )
        detailed = AuditExportContext(
            audit=audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions().plain_text()
        self.assertIn("DETAILED SNAP", detailed)

        with (
            patch.object(
                audit_knowledge_service,
                "get_knowledge_tree",
                side_effect=AssertionError("checklist nesmí live tree"),
            ),
            patch.object(
                audit_knowledge_service,
                "ensure_catalogs",
                side_effect=AssertionError("checklist nesmí ensure"),
            ),
        ):
            content = audit_terrain_checklist_service._checklist_content(audit.id)
        plain = content.plain_text()
        self.assertIn("DETAILED SNAP", plain)

    def test_tree_builder_preserves_order(self) -> None:
        from moduly.audity.sluzby.audit_question_source_service import (
            SnapshotAssertionView,
        )

        views = [
            SnapshotAssertionView(
                process_id="p1",
                process_name="P",
                section_id="s1",
                section_name="S",
                assertion_id="a2",
                assertion_text="druhá",
                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                severity="nizka",
                question_kind=AUDIT_QUESTION_KIND_LEGACY,
                display_order=20,
            ),
            SnapshotAssertionView(
                process_id="p1",
                process_name="P",
                section_id="s1",
                section_name="S",
                assertion_id="a1",
                assertion_text="první",
                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                severity="nizka",
                question_kind=AUDIT_QUESTION_KIND_LEGACY,
                display_order=10,
            ),
        ]
        roots = build_knowledge_tree_from_snapshot_views(views)
        questions = roots[0].children[0].section["auditni_tvrzeni"]
        self.assertEqual([q["id"] for q in questions], ["a1", "a2"])


if __name__ == "__main__":
    unittest.main()
