"""AUDIT-MANUAL-START-2: ruční Nový audit jako plán, ne okamžité zahájení."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-manual-start-2-"))

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
    from core.services.storage_service import storage_service
    from core.shared.verification_type import VERIFICATION_TYPE_DOCUMENTATION
    from moduly.audity.constants import (
        AUDIT_EXECUTION_REQUIRES_PREPARATION_MESSAGE,
        AUDIT_EXECUTION_REQUIRES_SAVE_THEN_PREPARE_MESSAGE,
        AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        AUDIT_METHODOLOGY_GENERATION_V2,
        AUDIT_QUESTION_KIND_EXTRAORDINARY,
        AUDIT_STATUS_PLANOVANO,
        AUDIT_STATUS_PROBIHA,
        CONTROL_POINT_SEVERITY_STREDNI,
    )
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_extraordinary_question_service import (
        audit_extraordinary_question_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_snapshot_backfill_service import (
        AUDIT_BACKFILL_STATUS_OTHER_GENERATION,
        _cheap_needs_legacy_backfill,
        classify_audit_backfill_state,
    )
    from moduly.audity.sluzby.audit_v2_create_service import (
        create_audit_with_v2_snapshot,
        create_manual_audit_with_v2_snapshot,
        prepare_planned_audit,
    )
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


class AuditManualStart2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._v2 = prepare_v2_audit_create()
        self._system_wp, self._operation_wp = self._v2.__enter__()

    def tearDown(self) -> None:
        self._v2.__exit__(None, None, None)

    def _manual(self, **fields):
        payload = {
            "title": "Ruční audit",
            "year": 2026,
            "workplace_id": self._operation_wp.id,
            "workplace_name": self._operation_wp.name,
        }
        payload.update(fields)
        return create_manual_audit_with_v2_snapshot(fields=payload)

    def test_01_empty_dates_stay_planned_without_snapshot(self) -> None:
        audit = self._manual()
        self.assertIsNone(audit.started_at)
        self.assertIsNone(audit.audit_date)
        self.assertEqual(audit.status, AUDIT_STATUS_PLANOVANO)
        self.assertIsNone(audit.questions_frozen_at)
        self.assertEqual(
            audit.methodology_generation,
            AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        )
        self.assertTrue(audit.number)
        self.assertIsNone(audit.program_visit_id)
        self.assertEqual(_snapshot_count(audit.id), 0)

    def test_02_planned_date_does_not_fill_started_at(self) -> None:
        audit = self._manual(audit_date=date(2026, 11, 3))
        self.assertEqual(audit.audit_date, date(2026, 11, 3))
        self.assertIsNone(audit.started_at)
        self.assertEqual(audit.status, AUDIT_STATUS_PLANOVANO)
        self.assertEqual(_snapshot_count(audit.id), 0)

    def test_03_explicit_started_at_is_kept_without_snapshot(self) -> None:
        started = date(2026, 9, 1)
        audit = self._manual(started_at=started, audit_date=date(2026, 9, 15))
        self.assertEqual(audit.started_at, started)
        self.assertEqual(audit.status, AUDIT_STATUS_PROBIHA)
        self.assertEqual(
            audit.methodology_generation,
            AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        )
        self.assertEqual(_snapshot_count(audit.id), 0)

    def test_04_prepare_manual_uses_all_processes_and_keeps_started_at(self) -> None:
        audit_extraordinary_question_service.create_question(
            question_text="Ruční mimořádné",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self._operation_wp.id],
        )
        started = date(2026, 9, 2)
        audit = self._manual(started_at=started)
        from moduly.audity.ui.audit_spis_widget import AuditSpisWidget

        widget = AuditSpisWidget()
        widget.load_audit(audit)
        self.assertFalse(widget.prepare_button.isHidden())
        widget.close()

        with patch(
            "moduly.audity.sluzby.audit_v2_create_service.prepare_planned_audit",
            wraps=prepare_planned_audit,
        ) as prepare:
            prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        self.assertIsNone(prepare.call_args.kwargs["planned_process_ids"])
        self.assertEqual(prepared.started_at, started)
        self.assertEqual(prepared.methodology_generation, AUDIT_METHODOLOGY_GENERATION_V2)
        self.assertIsNotNone(prepared.questions_frozen_at)
        self.assertGreater(_snapshot_count(prepared.id), 0)
        with get_session() as session:
            kinds = set(
                session.scalars(
                    select(AuditQuestionSnapshot.question_kind).where(
                        AuditQuestionSnapshot.audit_id == prepared.id
                    )
                )
            )
        self.assertIn(AUDIT_QUESTION_KIND_EXTRAORDINARY, kinds)

    def test_05_execution_gates(self) -> None:
        audit = self._manual()
        dialog = AuditDialog(audit=audit)
        blocked = dialog._execution_block_message(
            dialog.get_data() | {"conclusion_text": "Závěr"}
        )
        self.assertEqual(blocked, AUDIT_EXECUTION_REQUIRES_PREPARATION_MESSAGE)

        prepared = audit_program_service.prepare_audit_from_visit(audit.id)
        dialog.audit = prepared
        still = dialog._execution_block_message(
            dialog.get_data() | {"conclusion_text": "Závěr", "started_at": None}
        )
        self.assertIsNotNone(still)
        allowed = dialog._execution_block_message(
            dialog.get_data() | {"conclusion_text": "Závěr", "started_at": date(2026, 9, 3)}
        )
        self.assertIsNone(allowed)
        dialog.close()

    def test_06_unsaved_execution_does_not_point_only_at_prepare(self) -> None:
        from types import SimpleNamespace

        before = {item.id for item in audit_service.get_all()}
        dialog = AuditDialog.__new__(AuditDialog)
        dialog.audit = None
        dialog._visit_context = None
        from moduly.audity.sluzby.audit_deferred_edits import AuditDeferredEdits

        dialog._deferred = AuditDeferredEdits()
        dialog.commission_widget = SimpleNamespace(validate=lambda: (True, ""))
        dialog.processes_widget = SimpleNamespace(capture_section_summary=lambda: None)
        dialog.terrain_widget = SimpleNamespace(capture_section_summary=lambda: None)
        dialog.get_data = lambda: {
            "conclusion_text": "Rozpracovaný závěr",
            "started_at": None,
            "silne_stranky": "",
            "lead_auditor_recommendation": None,
        }
        with patch("moduly.audity.ui.audit_dialog.QMessageBox.warning") as warning, patch(
            "moduly.audity.ui.audit_dialog.create_manual_audit_with_v2_snapshot",
            side_effect=AssertionError("neuložený audit se nesmí zapsat"),
        ):
            saved = dialog._persist()
        self.assertFalse(saved)
        message = warning.call_args.args[2]
        self.assertEqual(message, AUDIT_EXECUTION_REQUIRES_SAVE_THEN_PREPARE_MESSAGE)
        self.assertNotIn("Připravit audit", message)
        self.assertEqual({item.id for item in audit_service.get_all()}, before)

    def test_07_backfill_does_not_freeze_manual_plan(self) -> None:
        audit = self._manual()
        item = classify_audit_backfill_state(audit, snapshot_rows=[], control_results=[])
        self.assertEqual(item.status, AUDIT_BACKFILL_STATUS_OTHER_GENERATION)
        self.assertFalse(_cheap_needs_legacy_backfill(storage_service.database_path))
        refreshed = audit_service.get_by_id(audit.id)
        assert refreshed is not None
        self.assertEqual(
            refreshed.methodology_generation,
            AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        )
        self.assertEqual(_snapshot_count(refreshed.id), 0)

    def test_08_existing_v2_manual_snapshot_stays(self) -> None:
        audit = create_audit_with_v2_snapshot(
            fields={
                "title": "Starý ruční",
                "year": 2026,
                "started_at": date(2026, 4, 1),
                "workplace_id": self._operation_wp.id,
            },
            workplace_id=self._operation_wp.id,
        )
        before = _snapshot_count(audit.id)
        frozen_at = audit.questions_frozen_at
        self.assertGreater(before, 0)
        again = audit_service.get_by_id(audit.id)
        assert again is not None
        self.assertEqual(_snapshot_count(again.id), before)
        self.assertEqual(again.questions_frozen_at, frozen_at)
        self.assertEqual(again.methodology_generation, AUDIT_METHODOLOGY_GENERATION_V2)
        self.assertEqual(again.started_at, date(2026, 4, 1))
