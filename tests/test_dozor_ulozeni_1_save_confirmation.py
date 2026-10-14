"""DOZOR-ULOZENI-1 – potvrzení úspěšného uložení ve Státním dozoru."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="dozor-ulozeni-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.statni_dozor.constants import (
        AUTHORITY_NAME_REQUIRED_MESSAGE,
        AUTHORITY_REQUIRED_MESSAGE,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
        control_authority_catalog_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.control_authority_dialog import ControlAuthorityDialog
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )

CONFIRMATION_TITLE = "Státní dozor"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class DozorUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.statni_dozor.ui.save_confirmation._exec_message_box",
            side_effect=_exec,
        ):
            action()
        return shown

    def _open(self, supervision_id: int | None = None) -> StateSupervisionEditorDialog:
        dialog = StateSupervisionEditorDialog(supervision_id=supervision_id)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog) -> None:
        dialog._editor._closing = True
        dialog.close()

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        dialog = self._open()
        dialog.authority_combo.setCurrentText("OIP uložení")
        dialog.file_number_edit.setText("ČJ-1")
        dialog.subject_edit.setPlainText("uložený předmět")
        shown = self._run(dialog._editor.save_button.click)
        self.assertEqual(len(shown), 1)
        box = shown[0]
        self.assertEqual(box.windowTitle(), CONFIRMATION_TITLE)
        self.assertEqual(box.text(), CONFIRMATION_TEXT)
        self.assertEqual(box.icon(), QMessageBox.Icon.Information)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        self.assertEqual(ok_button.text(), "OK")
        self.assertFalse(dialog._editor.is_dirty())
        self.assertTrue(dialog.isVisible())
        supervision_id = int(dialog.supervision_id)
        self._close(dialog)

        reopened = self._open(supervision_id)
        self.assertEqual(reopened.authority_combo.currentText(), "OIP uložení")
        self.assertEqual(reopened.file_number_edit.text(), "ČJ-1")
        self.assertEqual(reopened.subject_edit.toPlainText(), "uložený předmět")
        stored = state_supervision_service.get_supervision(supervision_id)
        self.assertEqual(stored.authority_name, "OIP uložení")
        self.assertEqual(stored.file_number, "ČJ-1")
        self.assertEqual(stored.subject, "uložený předmět")
        self._close(reopened)

    def test_save_without_changes_and_tab_switch_do_not_confirm(self) -> None:
        dialog = self._open()
        dialog.authority_combo.setCurrentText("OIP beze změny")
        first = self._run(dialog._editor.save_button.click)
        self.assertEqual(len(first), 1)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        second = self._run(dialog._editor._handle_save_clicked)
        self.assertEqual(second, [])
        switched = self._run(
            lambda: dialog.tabs.setCurrentIndex(
                next(
                    index
                    for index in range(dialog.tabs.count())
                    if dialog.tabs.tabText(index) == TAB_SUBJECT_PREPARATION
                )
            )
        )
        self.assertEqual(switched, [])
        self.assertEqual(dialog.authority_combo.currentText(), "OIP beze změny")
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        dialog = self._open()
        dialog.authority_combo.setCurrentText("OIP platný")
        dialog.subject_edit.setPlainText("původní předmět")
        self._run(dialog._editor.save_button.click)
        supervision_id = int(dialog.supervision_id)

        dialog.authority_combo.setCurrentText("")
        dialog.subject_edit.setPlainText("rozepsaný předmět")
        with patch(
            "moduly.statni_dozor.ui.state_supervision_editor_dialog.QMessageBox.warning"
        ) as warn:
            shown = self._run(dialog._editor.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn(AUTHORITY_REQUIRED_MESSAGE, warn.call_args.args)
        self.assertEqual(dialog.authority_combo.currentText(), "")
        self.assertEqual(dialog.subject_edit.toPlainText(), "rozepsaný předmět")
        self.assertTrue(dialog._editor.is_dirty())
        stored = state_supervision_service.get_supervision(supervision_id)
        self.assertEqual(stored.authority_name, "OIP platný")
        self.assertEqual(stored.subject, "původní předmět")
        self._close(dialog)

    def test_close_and_save_and_close_do_not_confirm(self) -> None:
        dialog = self._open()
        dialog.authority_combo.setCurrentText("OIP zavření")
        dialog.file_number_edit.setText("ČJ-zavřít")
        shown = self._run(dialog._save_close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        supervision_id = int(dialog.supervision_id)
        stored = state_supervision_service.get_supervision(supervision_id)
        self.assertEqual(stored.file_number, "ČJ-zavřít")

        clean = self._open(supervision_id)
        shown = self._run(clean._editor.close_button.click)
        self.assertEqual(shown, [])
        self.assertEqual(clean.result(), QDialog.DialogCode.Rejected)

        dirty = self._open(supervision_id)
        dirty.notification_note_edit.setPlainText("z promptu zavření")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ):
            shown = self._run(lambda: self.assertTrue(dirty._editor.request_close()))
        self.assertEqual(shown, [])
        stored = state_supervision_service.get_supervision(supervision_id)
        self.assertEqual(stored.notification_note, "z promptu zavření")
        self._close(dirty)

    def test_authority_editor_confirms_only_explicit_changed_save(self) -> None:
        dialog = ControlAuthorityDialog()
        dialog.show()
        self.app.processEvents()
        dialog.name_edit.setText("Orgán uložení")
        dialog.abbreviation_edit.setText("OU")
        shown = self._run(dialog._editor.save_button.click)
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0].windowTitle(), CONFIRMATION_TITLE)
        self.assertEqual(shown[0].text(), CONFIRMATION_TEXT)
        authority_id = int(dialog._authority.id)
        again = self._run(dialog._editor._handle_save_clicked)
        self.assertEqual(again, [])
        dialog._editor._closing = True
        dialog.close()

        failed = ControlAuthorityDialog(authority=control_authority_catalog_service.get_authority(authority_id))
        failed.show()
        self.app.processEvents()
        failed.name_edit.setText("")
        failed.abbreviation_edit.setText("rozepsaná")
        with patch(
            "moduly.statni_dozor.ui.control_authority_dialog.QMessageBox.warning"
        ) as warn:
            shown = self._run(failed._editor.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn(AUTHORITY_NAME_REQUIRED_MESSAGE, warn.call_args.args)
        self.assertEqual(failed.abbreviation_edit.text(), "rozepsaná")
        stored = control_authority_catalog_service.get_authority(authority_id)
        self.assertEqual(stored.name, "Orgán uložení")
        self.assertEqual(stored.abbreviation, "OU")
        failed._editor._closing = True
        failed.close()
