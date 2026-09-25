"""AUDIT-MANUAL-SCOPE-2: rozsah ručního auditu po řídicích procesech."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-manual-scope-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from sqlalchemy import func, select

    from core.database.session import get_session
    from core.shared.verification_type import VERIFICATION_TYPE_DOCUMENTATION
    from moduly.audity.constants import (
        AUDIT_QUESTION_KIND_EXTRAORDINARY,
        AUDIT_QUESTION_KIND_OPERATION,
        AUDIT_SCOPE_REQUIRED_MESSAGE,
        AUDIT_SCOPE_UNAVAILABLE_MESSAGE,
        CONTROL_POINT_SEVERITY_STREDNI,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.modely.audit_scope_process import AuditScopeProcess
    from moduly.audity.sluzby.audit_extraordinary_question_service import (
        audit_extraordinary_question_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import (
        KnowledgeTreeNode,
        audit_knowledge_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_scope_service import (
        list_audit_scope_processes,
        replace_audit_scope_processes,
        require_manual_planned_process_ids,
        snapshot_scope_labels,
    )
    from moduly.audity.sluzby.audit_v2_create_service import (
        create_audit_with_v2_snapshot,
        create_manual_audit_with_v2_snapshot,
        prepare_planned_audit,
    )
    from moduly.audity.ui.audit_spis_widget import AuditSpisWidget
    from tests.audit_v2a_test_support import prepare_v2_audit_create


def _question(qid: str, text: str) -> dict:
    return {
        "id": qid,
        "text": text,
        "aktivni": True,
        "poradi": 10,
        "verification_type": "dokumentace",
        "zavaznost": "stredni",
        "question_kind": AUDIT_QUESTION_KIND_OPERATION,
    }


def _tree(process_id: str, process_name: str, question_id: str) -> list:
    section = {
        "id": f"sec_{process_id}",
        "nazev": "Oblast",
        "aktivni": True,
        "auditni_tvrzeni": [_question(question_id, text=question_id)],
        "sekce": [],
    }
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
            children=(section_node,),
        )
    ]


def _snapshot_rows(audit_id: int) -> list[AuditQuestionSnapshot]:
    with get_session() as session:
        rows = list(
            session.scalars(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit_id
                )
            )
        )
        for row in rows:
            session.expunge(row)
        return rows


def _scope_ids(audit_id: int) -> list[str]:
    return [row.process_id for row in list_audit_scope_processes(audit_id)]


class AuditManualScope2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._v2 = prepare_v2_audit_create()
        self._system_wp, self._operation_wp = self._v2.__enter__()

    def tearDown(self) -> None:
        self._v2.__exit__(None, None, None)

    def _manual(self, scope: list[dict] | None = None):
        return create_manual_audit_with_v2_snapshot(
            fields={
                "workplace_id": self._operation_wp.id,
                "year": 2026,
                "title": "Ruční rozsah",
            },
            scope_processes=scope if scope is not None else [],
        )

    def _widget_with_catalog(self, selected: set[str] | None = None) -> AuditSpisWidget:
        processes = audit_knowledge_service.get_processes(ensure=True)
        widget = AuditSpisWidget()
        widget.show_editable_scope(
            [(item.id, item.nazev) for item in processes],
            selected or set(),
        )
        return widget

    def test_01_new_manual_scope_lists_active_processes_unchecked(self) -> None:
        processes = audit_knowledge_service.get_processes(ensure=True)
        widget = self._widget_with_catalog()
        shown = [box.property("process_id") for box in widget._scope_checks]
        self.assertEqual(shown, [item.id for item in processes])
        self.assertTrue(processes)
        self.assertEqual(widget.selected_scope(), [])
        self.assertIn("0 z", widget.scope_summary_label.text())
        widget.close()

    def test_02_one_process_survives_reopen(self) -> None:
        process = audit_knowledge_service.get_processes(ensure=True)[0]
        audit = self._manual(
            [{"process_id": process.id, "process_name": process.nazev, "display_order": 0}]
        )
        self.assertEqual(_scope_ids(audit.id), [process.id])
        again = list_audit_scope_processes(audit.id)
        self.assertEqual(again[0].process_name, process.nazev)

    def test_03_several_processes_match_selection(self) -> None:
        processes = audit_knowledge_service.get_processes(ensure=True)[:3]
        chosen = [
            {"process_id": item.id, "process_name": item.nazev, "display_order": index}
            for index, item in enumerate(processes)
        ]
        audit = self._manual(chosen)
        self.assertEqual(_scope_ids(audit.id), [item.id for item in processes])

    def test_04_select_all_and_clear_only_listed_processes(self) -> None:
        widget = self._widget_with_catalog()
        widget.select_all_scope()
        selected = {item["process_id"] for item in widget.selected_scope()}
        active = {item.id for item in audit_knowledge_service.get_processes(ensure=False)}
        self.assertEqual(selected, active)
        widget.clear_scope()
        self.assertEqual(widget.selected_scope(), [])
        widget.close()

    def test_05_prepare_without_scope_is_blocked(self) -> None:
        audit = self._manual([])
        before = len(_snapshot_rows(audit.id))
        with patch(
            "moduly.audity.sluzby.audit_v2_create_service.prepare_planned_audit",
            wraps=prepare_planned_audit,
        ) as prepare:
            with self.assertRaises(ValueError) as blocked:
                audit_program_service.prepare_audit_from_visit(audit.id)
        self.assertEqual(str(blocked.exception), AUDIT_SCOPE_REQUIRED_MESSAGE)
        prepare.assert_not_called()
        self.assertEqual(len(_snapshot_rows(audit.id)), before)
        self.assertEqual(_scope_ids(audit.id), [])

    def test_06_prepare_one_process_limits_snapshot(self) -> None:
        tree = _tree("proc_a", "Proces A", "q_a") + _tree("proc_b", "Proces B", "q_b")
        audit = self._manual(
            [{"process_id": "proc_a", "process_name": "Proces A"}]
        )
        with patch.object(audit_knowledge_service, "get_knowledge_tree", return_value=tree):
            prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        rows = [
            row
            for row in _snapshot_rows(prepared.id)
            if row.question_kind != AUDIT_QUESTION_KIND_EXTRAORDINARY
        ]
        self.assertEqual({row.process_id for row in rows}, {"proc_a"})
        self.assertEqual({row.assertion_id for row in rows}, {"q_a"})

    def test_07_prepare_several_processes_matches_scope(self) -> None:
        tree = _tree("proc_a", "Proces A", "q_a") + _tree("proc_b", "Proces B", "q_b")
        tree += _tree("proc_c", "Proces C", "q_c")
        audit = self._manual(
            [
                {"process_id": "proc_a", "process_name": "Proces A", "display_order": 0},
                {"process_id": "proc_c", "process_name": "Proces C", "display_order": 1},
            ]
        )
        with patch.object(audit_knowledge_service, "get_knowledge_tree", return_value=tree):
            prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        rows = [
            row
            for row in _snapshot_rows(prepared.id)
            if row.question_kind != AUDIT_QUESTION_KIND_EXTRAORDINARY
        ]
        self.assertEqual({row.process_id for row in rows}, {"proc_a", "proc_c"})
        self.assertEqual({row.assertion_id for row in rows}, {"q_a", "q_c"})

    def test_08_extraordinary_stays_workplace_based(self) -> None:
        audit_extraordinary_question_service.create_question(
            question_text="Mimořádné k rozsahu",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self._operation_wp.id],
        )
        tree = _tree("proc_a", "Proces A", "q_a")
        audit = self._manual([{"process_id": "proc_a", "process_name": "Proces A"}])
        with patch.object(audit_knowledge_service, "get_knowledge_tree", return_value=tree):
            prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        kinds = {row.question_kind for row in _snapshot_rows(prepared.id)}
        self.assertIn(AUDIT_QUESTION_KIND_EXTRAORDINARY, kinds)

    def test_09_scope_change_before_prepare_survives_reopen(self) -> None:
        audit = self._manual(
            [{"process_id": "proc_a", "process_name": "Proces A", "display_order": 0}]
        )
        replace_audit_scope_processes(
            audit.id,
            [
                {"process_id": "proc_b", "process_name": "Proces B", "display_order": 0},
                {"process_id": "proc_c", "process_name": "Proces C", "display_order": 1},
            ],
        )
        self.assertEqual(_scope_ids(audit.id), ["proc_b", "proc_c"])

    def test_10_prepared_scope_is_readonly_from_snapshot(self) -> None:
        tree = _tree("proc_a", "Proces A", "q_a")
        audit = self._manual([{"process_id": "proc_a", "process_name": "Proces A"}])
        with patch.object(audit_knowledge_service, "get_knowledge_tree", return_value=tree):
            prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        labels = snapshot_scope_labels(prepared.id)
        self.assertEqual(labels, [("proc_a", "Proces A")])
        widget = AuditSpisWidget()
        widget.show_readonly_scope(labels)
        self.assertFalse(widget.scope_select_all_button.isEnabled())
        self.assertFalse(widget._scope_checks[0].isEnabled())
        self.assertTrue(widget._scope_checks[0].isChecked())
        self.assertEqual(widget._scope_checks[0].text(), "Proces A")
        widget.close()

    def test_11_old_snapshot_without_scope_rows_opens_from_snapshot(self) -> None:
        tree = _tree("proc_old", "Starý proces", "q_old")
        audit = create_audit_with_v2_snapshot(
            fields={"year": 2026, "title": "Starý ruční", "started_at": date(2026, 1, 2)},
            workplace_id=self._operation_wp.id,
            planned_process_ids=["proc_old"],
            knowledge_tree=tree,
            ensure_knowledge=False,
        )
        self.assertEqual(_scope_ids(audit.id), [])
        labels = snapshot_scope_labels(audit.id)
        self.assertEqual(labels, [("proc_old", "Starý proces")])
        widget = AuditSpisWidget()
        widget.show_readonly_scope(labels)
        self.assertEqual(widget.selected_scope()[0]["process_name"], "Starý proces")
        widget.close()
        with get_session() as session:
            stored = session.scalar(
                select(func.count())
                .select_from(AuditScopeProcess)
                .where(AuditScopeProcess.audit_id == audit.id)
            )
        self.assertEqual(int(stored or 0), 0)

    def test_12_program_audit_does_not_use_manual_scope(self) -> None:
        program = audit_program_service.create_program(
            name="Program rozsah",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._operation_wp.id,
            workplace_name=self._operation_wp.name,
            audit_interval_months=12,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._operation_wp.id,
            planned_year=2026,
            planned_month=6,
        )
        audit_program_service.add_visit_process(
            visit.id, process_id="proc_a", process_name="Proces A"
        )
        audit = audit_program_service.create_audit_from_visit(visit.id, started_at=None)
        self.assertEqual(_scope_ids(audit.id), [])
        tree = _tree("proc_a", "Proces A", "q_a") + _tree("proc_b", "Proces B", "q_b")
        with patch(
            "moduly.audity.sluzby.audit_scope_service.require_manual_planned_process_ids",
            side_effect=AssertionError("ruční rozsah se u programu nesmí použít"),
        ):
            with patch.object(
                audit_knowledge_service, "get_knowledge_tree", return_value=tree
            ):
                prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        rows = [
            row
            for row in _snapshot_rows(prepared.id)
            if row.question_kind != AUDIT_QUESTION_KIND_EXTRAORDINARY
        ]
        self.assertEqual({row.process_id for row in rows}, {"proc_a"})
        self.assertEqual(_scope_ids(prepared.id), [])

    def test_13_unavailable_process_blocks_prepare(self) -> None:
        audit = self._manual(
            [{"process_id": "uz_neexistuje", "process_name": "Zrušený proces"}]
        )
        tree = _tree("proc_a", "Proces A", "q_a")
        with patch.object(audit_knowledge_service, "get_knowledge_tree", return_value=tree):
            with patch(
                "moduly.audity.sluzby.audit_v2_create_service.prepare_planned_audit",
                wraps=prepare_planned_audit,
            ) as prepare:
                with self.assertRaises(ValueError) as blocked:
                    audit_program_service.prepare_audit_from_visit(audit.id)
        self.assertIn("Zrušený proces", str(blocked.exception))
        self.assertIn(
            AUDIT_SCOPE_UNAVAILABLE_MESSAGE.split("{")[0].strip(),
            str(blocked.exception),
        )
        prepare.assert_not_called()
        self.assertEqual(_snapshot_rows(audit.id), [])
        with self.assertRaises(ValueError):
            require_manual_planned_process_ids(audit.id, tree)
