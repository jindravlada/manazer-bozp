"""AUDIT-PLANNING-PREP-1: plán, příprava a zahájení auditu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-planning-prep-1-"))

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
        CONTROL_POINT_SEVERITY_STREDNI,
        AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        AUDIT_METHODOLOGY_GENERATION_V2,
        AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_CURRENT,
        AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_FROZEN,
        AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_UNFROZEN,
        AUDIT_PROGRAM_START_AUDIT_BUTTON,
        AUDIT_STATUS_PLANOVANO,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_extraordinary_question_service import (
        audit_extraordinary_question_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_program_statements_export_context_service import (
        audit_program_statements_export_context_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_snapshot_backfill_service import (
        AUDIT_BACKFILL_STATUS_NEEDS_BACKFILL,
        AUDIT_BACKFILL_STATUS_OTHER_GENERATION,
        classify_audit_backfill_state,
    )
    from moduly.audity.sluzby.audit_v2_create_service import create_audit_with_v2_snapshot
    from moduly.audity.ui.audit_dialog import AuditDialog
    from tests.audit_v2a_test_support import prepare_v2_audit_create


def _snapshot_count(audit_id: int) -> int:
    with get_session() as session:
        total = session.scalar(
            select(func.count())
            .select_from(AuditQuestionSnapshot)
            .where(AuditQuestionSnapshot.audit_id == audit_id)
        )
    return int(total or 0)


class AuditPlanningPrep1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._v2 = prepare_v2_audit_create()
        self._system_wp, self._operation_wp = self._v2.__enter__()

    def tearDown(self) -> None:
        self._v2.__exit__(None, None, None)

    def _visit(self):
        program = audit_program_service.create_program(
            name="Program plán",
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
            planned_date=date(2026, 6, 15),
        )
        from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service

        tree = audit_knowledge_service.get_knowledge_tree(ensure=True)
        node = tree[0]
        audit_program_service.add_visit_process(
            visit.id,
            process_id=node.process_id,
            process_name=node.process_label,
        )
        return visit

    def test_01_plan_without_started_at_has_no_snapshot(self) -> None:
        visit = self._visit()
        audit = audit_program_service.create_audit_from_visit(visit.id, started_at=None)
        self.assertTrue(audit.number)
        self.assertIsNone(audit.started_at)
        self.assertEqual(audit.status, AUDIT_STATUS_PLANOVANO)
        self.assertIsNone(audit.questions_frozen_at)
        self.assertEqual(
            audit.methodology_generation,
            AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        )
        self.assertNotEqual(audit.methodology_source, "snapshot")
        self.assertEqual(_snapshot_count(audit.id), 0)
        refreshed = audit_program_service.repository.get_visit(visit.id)
        assert refreshed is not None
        self.assertEqual(refreshed.audit_id, audit.id)
        self.assertEqual(audit.audit_date, date(2026, 6, 15))

    def test_02_backfill_skips_planned_unfrozen_and_keeps_legacy(self) -> None:
        planned = Audit(
            year=2026,
            methodology_generation=AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        )
        planned.id = 1
        item = classify_audit_backfill_state(
            planned, snapshot_rows=[], control_results=[]
        )
        self.assertEqual(item.status, AUDIT_BACKFILL_STATUS_OTHER_GENERATION)
        self.assertEqual(item.detail, "planned-unfrozen-v1")

        legacy = Audit(year=2020)
        legacy.id = 2
        legacy_item = classify_audit_backfill_state(
            legacy, snapshot_rows=[], control_results=[]
        )
        self.assertEqual(legacy_item.status, AUDIT_BACKFILL_STATUS_NEEDS_BACKFILL)

    def test_03_print_live_then_unfrozen_then_snapshot(self) -> None:
        visit = self._visit()
        live = audit_program_statements_export_context_service.build_for_visit(visit.id)
        self.assertEqual(live.document_status, AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_CURRENT)
        self.assertTrue(live.rows)

        audit = audit_program_service.create_audit_from_visit(visit.id)
        unfrozen = audit_program_statements_export_context_service.build_for_visit(visit.id)
        self.assertEqual(
            unfrozen.document_status,
            AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_UNFROZEN,
        )
        self.assertTrue(unfrozen.rows)

        prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        frozen = audit_program_statements_export_context_service.build_for_visit(visit.id)
        self.assertIn(prepared.number, frozen.document_status)
        self.assertTrue(
            frozen.document_status.startswith(
                AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_FROZEN.split("{")[0]
            )
        )

    def test_04_prepare_freezes_v2_and_keeps_planned_status(self) -> None:
        visit = self._visit()
        audit_extraordinary_question_service.create_question(
            question_text="Před přípravou",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self._operation_wp.id],
        )
        audit = audit_program_service.create_audit_from_visit(visit.id)
        self.assertEqual(_snapshot_count(audit.id), 0)
        prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        self.assertEqual(prepared.methodology_generation, AUDIT_METHODOLOGY_GENERATION_V2)
        self.assertIsNotNone(prepared.questions_frozen_at)
        self.assertIsNone(prepared.started_at)
        self.assertEqual(prepared.status, AUDIT_STATUS_PLANOVANO)
        self.assertGreater(_snapshot_count(prepared.id), 0)
        self.assertEqual(prepared.audit_date, date(2026, 6, 15))

    def test_05_later_extraordinary_is_not_added(self) -> None:
        visit = self._visit()
        audit = audit_program_service.create_audit_from_visit(visit.id)
        prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        before = _snapshot_count(prepared.id)
        audit_extraordinary_question_service.create_question(
            question_text="Až po snapshotu",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self._operation_wp.id],
        )
        self.assertEqual(_snapshot_count(prepared.id), before)

    def test_06_execution_and_completion_gates(self) -> None:
        visit = self._visit()
        context = audit_program_service.get_visit_audit_context(visit.id)
        dialog = AuditDialog(visit_context=context)
        data = dialog.get_data()
        data["conclusion_text"] = "Závěr"
        self.assertIsNotNone(dialog._execution_block_message(data))

        audit = audit_program_service.create_audit_from_visit(visit.id)
        dialog.audit = audit
        self.assertIsNotNone(dialog._execution_block_message(dialog.get_data() | {"conclusion_text": "Závěr"}))

        prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        dialog.audit = prepared
        blocked = dialog._execution_block_message(
            dialog.get_data() | {"conclusion_text": "Závěr", "started_at": None}
        )
        self.assertIsNotNone(blocked)
        allowed = dialog._execution_block_message(
            dialog.get_data() | {"conclusion_text": "Závěr", "started_at": date(2026, 6, 1)}
        )
        self.assertIsNone(allowed)
        with patch("moduly.audity.ui.audit_dialog.QMessageBox.warning") as warning:
            self.assertFalse(dialog._complete_audit(finished_at=date(2026, 6, 2)))
        warning.assert_called()
        dialog.close()

    def test_07_prepared_without_start_can_print_checklist_source(self) -> None:
        visit = self._visit()
        audit = audit_program_service.create_audit_from_visit(visit.id)
        prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        context = audit_program_statements_export_context_service.build_for_visit(visit.id)
        self.assertIn(prepared.number, context.document_status)
        self.assertIsNone(prepared.started_at)
        self.assertEqual(prepared.status, AUDIT_STATUS_PLANOVANO)

    def test_08_existing_v2_snapshot_is_not_regenerated(self) -> None:
        audit = create_audit_with_v2_snapshot(
            fields={
                "title": "Ruční",
                "year": 2026,
                "workplace_id": self._operation_wp.id,
                "started_at": date(2026, 3, 1),
                "audit_date": date(2026, 3, 1),
            },
            workplace_id=self._operation_wp.id,
        )
        before = _snapshot_count(audit.id)
        frozen_at = audit.questions_frozen_at
        self.assertGreater(before, 0)
        item = classify_audit_backfill_state(audit, snapshot_rows=[], control_results=[])
        self.assertEqual(item.status, AUDIT_BACKFILL_STATUS_OTHER_GENERATION)
        again = audit_service.get_by_id(audit.id)
        assert again is not None
        self.assertEqual(_snapshot_count(again.id), before)
        self.assertEqual(again.questions_frozen_at, frozen_at)
        self.assertEqual(again.methodology_generation, AUDIT_METHODOLOGY_GENERATION_V2)

    def test_09_terminology(self) -> None:
        self.assertEqual(AUDIT_PROGRAM_START_AUDIT_BUTTON, "Založit plán auditu...")
        from moduly.audity.ui.audit_spis_widget import AuditSpisWidget
        from moduly.audity.ui.audit_table import AuditTable

        widget = AuditSpisWidget()
        labels = []
        from PySide6.QtWidgets import QLabel

        for label in widget.findChildren(QLabel):
            labels.append(label.text())
        self.assertIn("Plánované datum:", labels)
        self.assertNotIn("Datum auditu:", labels)
        table = AuditTable()
        headers = [
            table.horizontalHeaderItem(col).text()
            for col in range(table.columnCount())
            if table.horizontalHeaderItem(col) is not None
        ]
        self.assertIn("Plán datum", headers)
        widget.close()
        table.close()
