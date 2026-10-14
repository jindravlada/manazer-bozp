"""EXT-AUDIT-ULOZENI-1 – potvrzení úspěšného uložení externího auditu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="ext-audit-ulozeni-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.externi_audity.sluzby.external_audit_service import (
        external_audit_service,
    )
    from moduly.externi_audity.ui.external_audit_editor_dialog import (
        TAB_PROGRAM,
        ExternalAuditEditorDialog,
    )

CONFIRMATION_TITLE = "Externí audity"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class ExtAuditUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.externi_audity.ui.external_audit_editor_dialog._exec_message_box",
            side_effect=_exec,
        ):
            action()
        return shown

    def _open(self, audit_id: int | None = None) -> ExternalAuditEditorDialog:
        dialog = ExternalAuditEditorDialog(audit_id=audit_id)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog: ExternalAuditEditorDialog) -> None:
        dialog._closing = True
        dialog.close()

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        dialog = self._open()
        dialog.ico.setText("12345678")
        dialog.organization_name.setText("Uložená organizace")
        dialog.note.setPlainText("uložená poznámka")
        shown = self._run(dialog._save_btn.click)
        self.assertEqual(len(shown), 1)
        box = shown[0]
        self.assertEqual(box.windowTitle(), CONFIRMATION_TITLE)
        self.assertEqual(box.text(), CONFIRMATION_TEXT)
        self.assertEqual(box.icon(), QMessageBox.Icon.Information)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        self.assertEqual(ok_button.text(), "OK")
        self.assertFalse(dialog._is_dirty())
        self.assertTrue(dialog.isVisible())
        audit_id = int(dialog._draft.audit_id)
        self._close(dialog)

        reopened = self._open(audit_id)
        self.assertEqual(reopened.organization_name.text(), "Uložená organizace")
        self.assertEqual(reopened.note.toPlainText(), "uložená poznámka")
        self.assertEqual(reopened.ico.text(), "12345678")
        self._close(reopened)

    def test_save_without_changes_and_tab_switch_do_not_confirm(self) -> None:
        dialog = self._open()
        dialog.ico.setText("87654321")
        dialog.organization_name.setText("Beze změny")
        first = self._run(dialog._save_btn.click)
        self.assertEqual(len(first), 1)
        second = self._run(dialog._save_btn.click)
        self.assertEqual(second, [])
        switched = self._run(lambda: dialog.tabs.setCurrentIndex(TAB_PROGRAM))
        self.assertEqual(switched, [])
        self.assertEqual(dialog.organization_name.text(), "Beze změny")
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        dialog = self._open()
        dialog.ico.setText("11223344")
        dialog.organization_name.setText("Platný název")
        self._run(dialog._save_btn.click)
        audit_id = int(dialog._draft.audit_id)

        dialog.ico.setText("")
        dialog.organization_name.setText("rozepsaný název")
        with patch(
            "moduly.externi_audity.ui.external_audit_editor_dialog.QMessageBox.warning"
        ) as warn:
            shown = self._run(dialog._save_btn.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn("IČ organizace je povinné.", warn.call_args.args[2])
        self.assertEqual(dialog.organization_name.text(), "rozepsaný název")
        self.assertEqual(dialog.ico.text(), "")
        self.assertTrue(dialog._is_dirty())
        stored = external_audit_service.load_draft(audit_id)
        self.assertEqual(stored.organization_name, "Platný název")
        self.assertEqual(stored.organization_ico, "11223344")
        self._close(dialog)

    def test_save_and_close_and_editor_close_do_not_confirm(self) -> None:
        dialog = self._open()
        dialog.ico.setText("55667788")
        dialog.organization_name.setText("K zavření")
        shown = self._run(dialog._save_close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        audit_id = int(dialog._draft.audit_id)
        stored = external_audit_service.load_draft(audit_id)
        self.assertEqual(stored.organization_name, "K zavření")

        clean = self._open(audit_id)
        shown = self._run(clean._close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(clean.result(), QDialog.DialogCode.Rejected)

        dirty = self._open(audit_id)
        dirty.note.setPlainText("z promptu zavření")
        with patch(
            "moduly.externi_audity.ui.external_audit_editor_dialog.confirm_unsaved_editor_close",
            return_value="save",
        ):
            shown = self._run(dirty._close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dirty.result(), QDialog.DialogCode.Accepted)
        stored = external_audit_service.load_draft(audit_id)
        self.assertEqual(stored.note, "z promptu zavření")
