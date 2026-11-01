"""SD-02: uložení otevřené kontroly nesmí zrušit automatické vypořádání."""

from __future__ import annotations

import importlib
import os
import unittest
import uuid
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

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
        FINDING_STATUS_ORIGIN_MANUAL,
        FINDING_STATUS_ORIGIN_TASK,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_PRILEZITOST,
    )
    from core.shared.finding_display import FINDING_STATUS_LABELS
    from core.shared.sluzby.finding_service import finding_service
    from moduly.statni_dozor.constants import COL_FINDING_STATUS
    from moduly.statni_dozor.sluzby.state_supervision_finding_task_service import (
        state_supervision_finding_task_service as ss_task,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


_COMPLETED = date(2026, 11, 18)
_CHECKED = date(2026, 11, 24)
_MANUAL_DATE = date(2026, 12, 15)


class StateSupervisionFindingSettlementSd02TestCase(unittest.TestCase):
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

    def _supervision(self):
        return state_supervision_service.create_supervision(
            authority_name=f"Orgán {self.marker}",
            subject="Kontrola vypořádání",
        )

    def _finding(self, parent_id: int, *, finding_type: str, description: str):
        return finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent_id,
            finding_type=finding_type,
            description=description,
            status=FINDING_STATUS_V_PROCESU,
            source_area_label="Původní oblast",
        )

    def _open(self, supervision_id: int) -> StateSupervisionEditorDialog:
        return StateSupervisionEditorDialog(supervision_id=supervision_id)

    def _settle_task(self, task_id: int) -> None:
        task = task_service.get_task_by_id(task_id)
        self.assertIsNotNone(task)
        saved = task_service.update_task(
            task_id=task_id,
            title=task.title,
            description=task.description or "",
            priority=task.priority or "Kritická",
            due_date=task.due_date,
            completed=True,
            completed_date=_COMPLETED,
            requires_verification=True,
            check_due_date=_CHECKED,
            checked_date=_CHECKED,
        )
        self.assertIsNotNone(saved)
        self.assertTrue(saved.requires_verification)
        self.assertEqual(saved.checked_date, _CHECKED)

    def _complete_task_dialog(self, dialog: TaskDialog) -> int:
        dialog.completed_checkbox.setChecked(True)
        dialog.completed_date_edit.set_date_value(_COMPLETED)
        dialog._completed_changed()
        dialog.checked_date_edit.set_date_value(_CHECKED)
        dialog._refresh_status()
        self.assertTrue(dialog._persist())
        self.assertEqual(dialog.status_label.text(), "Ukončeno")
        return QDialog.DialogCode.Accepted

    def test_01_open_editor_save_keeps_automatic_settlement(self) -> None:
        parent = self._supervision()
        finding = self._finding(
            parent.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            description="Evidence prohlídek ve více přehledech",
        )
        task = ss_task.create_task_for_finding(finding.id)
        editor = self._open(parent.id)
        draft = editor._findings_drafts[0]
        self.assertEqual(draft.status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(draft.resolved_at)
        self.assertEqual(
            editor.findings_table.item(0, COL_FINDING_STATUS).text(),
            FINDING_STATUS_LABELS[FINDING_STATUS_V_PROCESU],
        )

        self._settle_task(task.id)
        stored = finding_service.get_by_id(finding.id)
        self.assertEqual(stored.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(stored.resolved_at, date.today())
        self.assertNotEqual(stored.resolved_at, _CHECKED)
        self.assertEqual(editor._findings_drafts[0].status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(editor._findings_drafts[0].resolved_at)

        self.assertTrue(editor._persist())
        kept = finding_service.get_by_id(finding.id)
        self.assertEqual(kept.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(kept.resolved_at, date.today())
        self.assertNotEqual(kept.resolved_at, _CHECKED)
        self.assertEqual(kept.description, "Evidence prohlídek ve více přehledech")
        history = finding_service.status_history(finding.id)
        self.assertEqual(history[-1].new_status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(history[-1].origin, FINDING_STATUS_ORIGIN_TASK)
        self.assertNotIn(
            FINDING_STATUS_ORIGIN_MANUAL,
            [row.origin for row in history],
        )
        editor.close()

    def test_02_task_dialog_refreshes_open_editor(self) -> None:
        parent = self._supervision()
        finding = self._finding(
            parent.id,
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="Neaktuální měření",
        )
        ss_task.create_task_for_finding(finding.id)
        editor = self._open(parent.id)
        editor._select_finding_key(f"db-{finding.id}")

        with patch.object(
            TaskDialog,
            "exec",
            lambda dialog: self._complete_task_dialog(dialog),
        ):
            editor._open_finding_task()

        draft = editor._findings_drafts[0]
        self.assertEqual(draft.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(draft.resolved_at, date.today())
        self.assertNotEqual(draft.resolved_at, _CHECKED)
        self.assertEqual(
            editor.findings_table.item(0, COL_FINDING_STATUS).text(),
            FINDING_STATUS_LABELS[FINDING_STATUS_VYPORADANO],
        )
        self.assertFalse(editor._editor.is_dirty())

        self.assertTrue(editor._persist())
        kept = finding_service.get_by_id(finding.id)
        self.assertEqual(kept.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(kept.resolved_at, date.today())
        editor.close()

    def test_03_manual_status_change_is_stored(self) -> None:
        parent = self._supervision()
        finding = self._finding(
            parent.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            description="Ruční návrat stavu",
        )
        ss_task.create_task_for_finding(finding.id)
        editor = self._open(parent.id)
        editor._select_finding_key(f"db-{finding.id}")
        with patch.object(
            TaskDialog,
            "exec",
            lambda dialog: self._complete_task_dialog(dialog),
        ):
            editor._open_finding_task()
        self.assertEqual(editor._findings_drafts[0].status, FINDING_STATUS_VYPORADANO)

        def _manual(parent_widget, *, draft, is_new=False):
            del parent_widget, is_new
            return replace(
                draft,
                status=FINDING_STATUS_V_PROCESU,
                resolved_at=None,
                description="Ruční návrat stavu, upravený popis",
            )

        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            _manual,
        ):
            editor._edit_selected_finding()

        self.assertTrue(editor._editor.is_dirty())
        self.assertTrue(editor._persist())
        stored = finding_service.get_by_id(finding.id)
        self.assertEqual(stored.status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(stored.resolved_at)
        self.assertEqual(stored.description, "Ruční návrat stavu, upravený popis")
        history = finding_service.status_history(finding.id)
        self.assertEqual(history[-1].old_status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(history[-1].new_status, FINDING_STATUS_V_PROCESU)
        self.assertEqual(history[-1].origin, FINDING_STATUS_ORIGIN_MANUAL)
        self.assertIsNone(history[-1].resolved_at_after)
        editor.close()

    def test_04_other_fields_save_and_manual_date_wins(self) -> None:
        parent = self._supervision()
        finding = self._finding(
            parent.id,
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="Původní popis",
        )
        task = ss_task.create_task_for_finding(finding.id)
        editor = self._open(parent.id)
        self._settle_task(task.id)
        editor._select_finding_key(f"db-{finding.id}")

        def _edit_details(parent_widget, *, draft, is_new=False):
            del parent_widget, is_new
            return replace(
                draft,
                description="Upravený popis bez změny stavu",
                source_area_label="Nová oblast",
                recommended_action="Doplněné opatření",
            )

        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            _edit_details,
        ):
            editor._edit_selected_finding()

        self.assertEqual(editor._findings_drafts[0].status, FINDING_STATUS_V_PROCESU)
        self.assertTrue(editor._persist())
        stored = finding_service.get_by_id(finding.id)
        self.assertEqual(stored.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(stored.resolved_at, date.today())
        self.assertNotEqual(stored.resolved_at, _CHECKED)
        self.assertEqual(stored.description, "Upravený popis bez změny stavu")
        self.assertEqual(stored.source_area_label, "Nová oblast")
        self.assertEqual(stored.recommended_action, "Doplněné opatření")

        reopened = self._open(parent.id)
        reopened._select_finding_key(f"db-{finding.id}")

        def _manual_date(parent_widget, *, draft, is_new=False):
            del parent_widget, is_new
            return replace(
                draft,
                status=FINDING_STATUS_VYPORADANO,
                resolved_at=_MANUAL_DATE,
            )

        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            _manual_date,
        ):
            reopened._edit_selected_finding()

        self.assertTrue(reopened._persist())
        manual = finding_service.get_by_id(finding.id)
        self.assertEqual(manual.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(manual.resolved_at, _MANUAL_DATE)
        self.assertEqual(manual.description, "Upravený popis bez změny stavu")
        editor.close()
        reopened.close()

    def test_05_untouched_sibling_keeps_its_status(self) -> None:
        parent = self._supervision()
        settled = self._finding(
            parent.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            description="Má se vypořádat",
        )
        untouched = self._finding(
            parent.id,
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="Zůstává v procesu",
        )
        task = ss_task.create_task_for_finding(settled.id)
        editor = self._open(parent.id)
        self._settle_task(task.id)
        self.assertTrue(editor._persist())
        self.assertEqual(
            finding_service.get_by_id(settled.id).status,
            FINDING_STATUS_VYPORADANO,
        )
        sibling = finding_service.get_by_id(untouched.id)
        self.assertEqual(sibling.status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(sibling.resolved_at)
        self.assertEqual(sibling.description, "Zůstává v procesu")
        editor.close()
