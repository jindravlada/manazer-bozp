"""SD-04: vyplněné administrativní uzavření převede kontrolu na Uzavřena."""

from __future__ import annotations

import importlib
import os
import unittest
import uuid
from datetime import datetime
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
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.statni_dozor.constants import (
        CLOSED_AT_REQUIRED_MESSAGE,
        STATUS_ANNOUNCED,
        STATUS_CLOSED,
        STATUS_IN_PROGRESS,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )


_CONFIRM = (
    "moduly.statni_dozor.ui.state_supervision_editor_dialog.confirm_supervision_closure"
)
_CLOSED_AT = datetime(2026, 11, 2, 9, 30, 0)


class StateSupervisionAdminCloseSd04TestCase(unittest.TestCase):
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

    def _supervision(self, **fields):
        payload = {
            "authority_name": f"Orgán {self.marker}",
            "subject": "Administrativní uzavření",
        }
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _finding(self, parent_id: int, *, status: str, description: str):
        return finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent_id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=description,
            status=status,
        )

    def _open(self, supervision_id: int) -> StateSupervisionEditorDialog:
        return StateSupervisionEditorDialog(supervision_id=supervision_id)

    def _fill_closed_at(self, dialog: StateSupervisionEditorDialog) -> None:
        dialog.closed_at_edit.set_datetime(_CLOSED_AT)
        dialog._editor.refresh_dirty()

    def test_01_new_closed_at_closes_without_warning_when_findings_are_settled(self) -> None:
        parent = self._supervision()
        self._finding(
            parent.id,
            status=FINDING_STATUS_VYPORADANO,
            description="Už vypořádané",
        )
        dialog = self._open(parent.id)
        dialog.subject_edit.setPlainText("Poznámka k uzavření")
        self._fill_closed_at(dialog)
        self.assertEqual(dialog.get_data()["status"], STATUS_ANNOUNCED)
        with patch(_CONFIRM) as confirm:
            self.assertTrue(dialog._editor._run_save())
            confirm.assert_not_called()
        loaded = state_supervision_service.get_supervision(parent.id)
        self.assertEqual(loaded.status, STATUS_CLOSED)
        self.assertEqual(loaded.closed_at, _CLOSED_AT)
        self.assertEqual(loaded.subject, "Poznámka k uzavření")
        dialog.close()

        again = self._open(parent.id)
        self.assertEqual(again.get_data()["status"], STATUS_CLOSED)
        self.assertEqual(again.closed_at_edit.get_datetime(), _CLOSED_AT)
        again.file_number_edit.setText("SD-04")
        with patch(_CONFIRM) as confirm:
            self.assertTrue(again._editor._run_save())
            confirm.assert_not_called()
        repeated = state_supervision_service.get_supervision(parent.id)
        self.assertEqual(repeated.status, STATUS_CLOSED)
        self.assertEqual(repeated.closed_at, _CLOSED_AT)
        self.assertEqual(repeated.file_number, "SD-04")
        again.close()

    def test_02_open_findings_require_confirmation(self) -> None:
        parent = self._supervision()
        finding = self._finding(
            parent.id,
            status=FINDING_STATUS_OTEVRENE,
            description="Ještě otevřené",
        )
        dialog = self._open(parent.id)
        dialog.subject_edit.setPlainText("Rozpracovaný text")
        self._fill_closed_at(dialog)
        with patch(_CONFIRM, return_value=False) as confirm:
            self.assertFalse(dialog._editor._run_save())
            confirm.assert_called_once()
            self.assertEqual(confirm.call_args.args[1].open_findings_count, 1)
        kept = state_supervision_service.get_supervision(parent.id)
        self.assertEqual(kept.status, STATUS_ANNOUNCED)
        self.assertIsNone(kept.closed_at)
        self.assertEqual(dialog.subject_edit.toPlainText(), "Rozpracovaný text")
        self.assertEqual(dialog.closed_at_edit.get_datetime(), _CLOSED_AT)
        self.assertEqual(dialog.get_data()["status"], STATUS_CLOSED)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertEqual(
            finding_service.get_by_id(finding.id).status,
            FINDING_STATUS_OTEVRENE,
        )

        with patch(_CONFIRM, return_value=True) as confirm:
            self.assertTrue(dialog._editor._run_save())
            confirm.assert_called_once()
        closed = state_supervision_service.get_supervision(parent.id)
        self.assertEqual(closed.status, STATUS_CLOSED)
        self.assertEqual(closed.closed_at, _CLOSED_AT)
        self.assertEqual(closed.subject, "Rozpracovaný text")
        dialog.close()

        reopened = self._open(parent.id)
        self.assertEqual(reopened.get_data()["status"], STATUS_CLOSED)
        self.assertEqual(reopened.closed_at_edit.get_datetime(), _CLOSED_AT)
        reopened.close()

    def test_03_empty_date_does_not_change_status(self) -> None:
        parent = self._supervision(status=STATUS_IN_PROGRESS)
        dialog = self._open(parent.id)
        dialog.subject_edit.setPlainText("Jen předmět")
        with patch(_CONFIRM) as confirm:
            self.assertTrue(dialog._editor._run_save())
            confirm.assert_not_called()
        loaded = state_supervision_service.get_supervision(parent.id)
        self.assertEqual(loaded.status, STATUS_IN_PROGRESS)
        self.assertIsNone(loaded.closed_at)
        self.assertEqual(loaded.subject, "Jen předmět")
        dialog.close()

    def test_04_clearing_date_does_not_reopen_closed_control(self) -> None:
        parent = self._supervision(status=STATUS_CLOSED, closed_at=_CLOSED_AT)
        dialog = self._open(parent.id)
        dialog.closed_at_edit.set_datetime(None)
        with (
            patch(_CONFIRM) as confirm,
            patch.object(QMessageBox, "warning") as warning,
        ):
            self.assertFalse(dialog._editor._run_save())
            confirm.assert_not_called()
            self.assertIn(CLOSED_AT_REQUIRED_MESSAGE, warning.call_args.args)
        loaded = state_supervision_service.get_supervision(parent.id)
        self.assertEqual(loaded.status, STATUS_CLOSED)
        self.assertEqual(loaded.closed_at, _CLOSED_AT)
        self.assertEqual(dialog.get_data()["status"], STATUS_CLOSED)
        dialog.close()

    def test_05_manual_reopen_stays_available(self) -> None:
        parent = self._supervision(status=STATUS_CLOSED, closed_at=_CLOSED_AT)
        dialog = self._open(parent.id)
        dialog.status_combo.setCurrentIndex(
            dialog.status_combo.findData(STATUS_IN_PROGRESS)
        )
        dialog.closed_at_edit.set_datetime(None)
        with patch(_CONFIRM) as confirm:
            self.assertTrue(dialog._editor._run_save())
            confirm.assert_not_called()
        loaded = state_supervision_service.get_supervision(parent.id)
        self.assertEqual(loaded.status, STATUS_IN_PROGRESS)
        self.assertIsNone(loaded.closed_at)
        dialog.close()

        fresh = self._open(parent.id)
        self.assertEqual(fresh.get_data()["status"], STATUS_IN_PROGRESS)
        self.assertIsNone(fresh.closed_at_edit.get_datetime())
        self._fill_closed_at(fresh)
        with patch(_CONFIRM) as confirm:
            self.assertTrue(fresh._editor._run_save())
            confirm.assert_not_called()
        closed_again = state_supervision_service.get_supervision(parent.id)
        self.assertEqual(closed_again.status, STATUS_CLOSED)
        self.assertEqual(closed_again.closed_at, _CLOSED_AT)
        fresh.close()
