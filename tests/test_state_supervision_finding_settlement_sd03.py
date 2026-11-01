"""SD-03: stav zjištění a datum vypořádání musejí sedět."""

from __future__ import annotations

import importlib
import os
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_PRILEZITOST,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.statni_dozor.constants import (
        FINDING_RESOLVED_DATE_CONFLICT_MESSAGE,
        FINDING_RESOLVED_DATE_REQUIRED_MESSAGE,
    )
    from moduly.statni_dozor.sluzby.state_supervision_finding_task_service import (
        state_supervision_finding_task_service as ss_task,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_finding_dialog import (
        StateSupervisionFindingDialog,
        finding_settlement_conflict,
    )
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )
    from moduly.ukoly.sluzby.task_service import task_service


_CHECKED = date(2026, 11, 24)
_MANUAL_DATE = date(2026, 12, 15)


class StateSupervisionFindingSettlementSd03TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        cls._app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]

    def _dialog(self, **fields) -> StateSupervisionFindingDialog:
        payload = {
            "finding_type": FINDING_TYPE_PRILEZITOST,
            "description": "Popis zjištění",
            "status": FINDING_STATUS_V_PROCESU,
        }
        payload.update(fields)
        return StateSupervisionFindingDialog(
            draft=StateSupervisionFindingDraft(**payload),
            is_new=False,
        )

    def _set_status(self, dialog: StateSupervisionFindingDialog, status: str) -> None:
        dialog.status_combo.setCurrentIndex(dialog.status_combo.findData(status))

    def _warn_on_save(self, dialog: StateSupervisionFindingDialog) -> str | None:
        with patch.object(QMessageBox, "warning") as warning:
            dialog._on_save()
        self.assertIsNone(dialog.result_draft)
        if not warning.called:
            return None
        return warning.call_args.args[2]

    def test_01_manual_settlement_prefills_today_and_keeps_user_date(self) -> None:
        dialog = self._dialog()
        self._set_status(dialog, FINDING_STATUS_VYPORADANO)
        self.assertEqual(dialog.resolved_at_edit.get_date(), date.today())
        self.assertEqual(dialog.status_combo.currentData(), FINDING_STATUS_VYPORADANO)
        dialog.resolved_at_edit.set_date_value(_MANUAL_DATE)
        dialog._on_save()
        saved = dialog.result_draft
        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(saved.resolved_at, _MANUAL_DATE)
        dialog.close()

    def test_02_leaving_settled_status_clears_date(self) -> None:
        dialog = self._dialog(
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 10, 31),
        )
        self.assertEqual(dialog.resolved_at_edit.get_date(), date(2026, 10, 31))
        self._set_status(dialog, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(dialog.resolved_at_edit.get_date())
        self.assertEqual(dialog.status_combo.currentData(), FINDING_STATUS_V_PROCESU)
        dialog._on_save()
        self.assertEqual(dialog.result_draft.status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(dialog.result_draft.resolved_at)

        again = self._dialog(
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 10, 31),
        )
        self._set_status(again, FINDING_STATUS_OTEVRENE)
        self.assertIsNone(again.resolved_at_edit.get_date())
        again.close()
        dialog.close()

    def test_03_date_without_settled_status_is_refused(self) -> None:
        dialog = self._dialog(status=FINDING_STATUS_OTEVRENE)
        dialog.resolved_at_edit.set_date_value(_MANUAL_DATE)
        self.assertEqual(
            self._warn_on_save(dialog),
            FINDING_RESOLVED_DATE_CONFLICT_MESSAGE,
        )
        self.assertEqual(dialog.status_combo.currentData(), FINDING_STATUS_OTEVRENE)
        self.assertEqual(dialog.resolved_at_edit.get_date(), _MANUAL_DATE)

        in_process = self._dialog()
        in_process.resolved_at_edit.set_date_value(_CHECKED)
        self.assertEqual(
            self._warn_on_save(in_process),
            FINDING_RESOLVED_DATE_CONFLICT_MESSAGE,
        )
        self.assertEqual(in_process.status_combo.currentData(), FINDING_STATUS_V_PROCESU)
        dialog.close()
        in_process.close()

    def test_04_settled_status_without_date_is_refused(self) -> None:
        dialog = self._dialog(
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 10, 31),
        )
        dialog.resolved_at_edit.clear_date()
        self.assertEqual(
            self._warn_on_save(dialog),
            FINDING_RESOLVED_DATE_REQUIRED_MESSAGE,
        )
        self.assertEqual(dialog.status_combo.currentData(), FINDING_STATUS_VYPORADANO)
        dialog.close()

    def test_05_editor_save_reopen_and_task_settlement_stay_consistent(self) -> None:
        parent = state_supervision_service.create_supervision(
            authority_name=f"Orgán {self.marker}",
            subject="Konzistence vypořádání",
        )
        finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            description="Ruční vypořádání",
            status=FINDING_STATUS_V_PROCESU,
        )
        editor = StateSupervisionEditorDialog(supervision_id=parent.id)
        editor._select_finding_key(f"db-{finding.id}")

        def _settle(parent_widget, *, draft, is_new=False):
            dialog = StateSupervisionFindingDialog(
                parent_widget, draft=draft, is_new=is_new
            )
            self._set_status(dialog, FINDING_STATUS_VYPORADANO)
            dialog.resolved_at_edit.set_date_value(_MANUAL_DATE)
            dialog._on_save()
            result = dialog.result_draft
            dialog.close()
            return result

        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            _settle,
        ):
            editor._edit_selected_finding()
        self.assertTrue(editor._persist())
        editor.close()

        reopened = StateSupervisionEditorDialog(supervision_id=parent.id)
        loaded = reopened._findings_drafts[0]
        self.assertEqual(loaded.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(loaded.resolved_at, _MANUAL_DATE)
        reopened._select_finding_key(loaded.client_key)

        def _reopen_status(parent_widget, *, draft, is_new=False):
            dialog = StateSupervisionFindingDialog(
                parent_widget, draft=draft, is_new=is_new
            )
            self._set_status(dialog, FINDING_STATUS_V_PROCESU)
            dialog._on_save()
            result = dialog.result_draft
            dialog.close()
            return result

        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            _reopen_status,
        ):
            reopened._edit_selected_finding()
        self.assertIsNone(reopened._findings_drafts[0].resolved_at)
        self.assertTrue(reopened._persist())
        reopened.close()

        stored = finding_service.get_by_id(finding.id)
        self.assertEqual(stored.status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(stored.resolved_at)

        task = ss_task.create_task_for_finding(finding.id)
        fresh = StateSupervisionEditorDialog(supervision_id=parent.id)
        self.assertEqual(fresh._findings_drafts[0].status, FINDING_STATUS_V_PROCESU)
        current = task_service.get_task_by_id(task.id)
        task_service.update_task(
            task_id=task.id,
            title=current.title,
            description=current.description or "",
            priority=current.priority or "Kritická",
            due_date=current.due_date,
            completed=True,
            completed_date=date(2026, 11, 18),
            requires_verification=True,
            check_due_date=_CHECKED,
            checked_date=_CHECKED,
        )
        self.assertEqual(
            finding_service.get_by_id(finding.id).status,
            FINDING_STATUS_VYPORADANO,
        )
        self.assertEqual(finding_service.get_by_id(finding.id).resolved_at, date.today())
        self.assertNotEqual(
            finding_service.get_by_id(finding.id).resolved_at,
            _CHECKED,
        )
        self.assertTrue(fresh._persist())
        kept = finding_service.get_by_id(finding.id)
        self.assertEqual(kept.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(kept.resolved_at, date.today())
        fresh.close()

        final = StateSupervisionEditorDialog(supervision_id=parent.id)
        self.assertEqual(final._findings_drafts[0].status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(final._findings_drafts[0].resolved_at, date.today())
        final.close()

    def test_06_control_save_rejects_inconsistent_manual_draft(self) -> None:
        parent = state_supervision_service.create_supervision(
            authority_name=f"Orgán {self.marker}",
            subject="Zamítnutý rozpor",
        )
        finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="Bez data ve stavu v procesu",
            status=FINDING_STATUS_V_PROCESU,
        )
        editor = StateSupervisionEditorDialog(supervision_id=parent.id)
        editor._findings_drafts[0] = StateSupervisionFindingDraft(
            id=finding.id,
            client_key=editor._findings_drafts[0].client_key,
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="Bez data ve stavu v procesu",
            status=FINDING_STATUS_V_PROCESU,
            resolved_at=_MANUAL_DATE,
        )
        self.assertEqual(
            finding_settlement_conflict(
                FINDING_STATUS_V_PROCESU,
                _MANUAL_DATE,
            ),
            FINDING_RESOLVED_DATE_CONFLICT_MESSAGE,
        )
        with patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(editor._persist())
        self.assertIn(
            FINDING_RESOLVED_DATE_CONFLICT_MESSAGE,
            warning.call_args.args[2],
        )
        stored = finding_service.get_by_id(finding.id)
        self.assertEqual(stored.status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(stored.resolved_at)
        editor.close()

    def test_07_only_date_change_on_settled_finding_is_kept(self) -> None:
        parent = state_supervision_service.create_supervision(
            authority_name=f"Orgán {self.marker}",
            subject="Jen datum",
        )
        finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="Už vypořádané",
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 10, 1),
        )
        editor = StateSupervisionEditorDialog(supervision_id=parent.id)
        editor._select_finding_key(f"db-{finding.id}")

        def _change_date(parent_widget, *, draft, is_new=False):
            dialog = StateSupervisionFindingDialog(
                parent_widget, draft=draft, is_new=is_new
            )
            self.assertEqual(dialog.status_combo.currentData(), FINDING_STATUS_VYPORADANO)
            dialog.resolved_at_edit.set_date_value(_MANUAL_DATE)
            dialog._on_save()
            result = dialog.result_draft
            dialog.close()
            return result

        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            _change_date,
        ):
            editor._edit_selected_finding()
        self.assertTrue(editor._persist())
        editor.close()
        reopened = StateSupervisionEditorDialog(supervision_id=parent.id)
        self.assertEqual(reopened._findings_drafts[0].status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(reopened._findings_drafts[0].resolved_at, _MANUAL_DATE)
        self.assertEqual(reopened._findings_drafts[0].description, "Už vypořádané")
        reopened.close()
