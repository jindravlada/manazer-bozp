"""AUDIT-MIMORADNE-ULOZENI-1 – potvrzení uložení mimořádné otázky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="audit-mimoradne-ulozeni-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.verification_type import VERIFICATION_TYPE_DOCUMENTATION
    from moduly.audity.constants import (
        CONTROL_POINT_SEVERITY_STREDNI,
        EXTRAORDINARY_QUESTION_TEXT_REQUIRED,
    )
    from moduly.audity.sluzby.audit_extraordinary_question_service import (
        audit_extraordinary_question_service,
    )
    from moduly.audity.ui.extraordinary_question_editor_dialog import (
        ExtraordinaryQuestionEditorDialog,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service

CONFIRMATION_TITLE = "Interní audity"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class AuditMimoradneUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.workplace = settings_service.save_workplace(
            name="Provoz mimořádné",
            active=True,
            audit_enabled=True,
        )

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.audity.ui.extraordinary_question_editor_dialog._exec_message_box",
            side_effect=_exec,
        ):
            action()
        return shown

    def _open(self, question_id: int | None = None) -> ExtraordinaryQuestionEditorDialog:
        dialog = ExtraordinaryQuestionEditorDialog(question_id=question_id)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog: ExtraordinaryQuestionEditorDialog) -> None:
        dialog._closing = True
        dialog.close()

    def _fill(self, dialog: ExtraordinaryQuestionEditorDialog, text: str) -> None:
        dialog.question_text.setPlainText(text)
        dialog.severity_combo.setCurrentIndex(
            dialog.severity_combo.findData(CONTROL_POINT_SEVERITY_STREDNI)
        )
        dialog.verification_type_combo.setCurrentIndex(
            dialog.verification_type_combo.findData(VERIFICATION_TYPE_DOCUMENTATION)
        )
        dialog.mode_selected.setChecked(True)
        for row in range(dialog.workplace_list.count()):
            item = dialog.workplace_list.item(row)
            checked = int(item.data(Qt.ItemDataRole.UserRole)) == int(self.workplace.id)
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )

    def _checked_ids(self, dialog: ExtraordinaryQuestionEditorDialog) -> list[int]:
        ids: list[int] = []
        for row in range(dialog.workplace_list.count()):
            item = dialog.workplace_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return ids

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        dialog = self._open()
        self._fill(dialog, "Uložená otázka")
        dialog.note.setPlainText("uložená poznámka")
        dialog.assigned_by.setText("auditor")
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
        question_id = int(dialog.question_id)
        self.assertEqual(self._checked_ids(dialog), [int(self.workplace.id)])
        self._close(dialog)

        reopened = self._open(question_id)
        self.assertEqual(reopened.question_text.toPlainText(), "Uložená otázka")
        self.assertEqual(reopened.note.toPlainText(), "uložená poznámka")
        self.assertEqual(reopened.assigned_by.text(), "auditor")
        self.assertEqual(self._checked_ids(reopened), [int(self.workplace.id)])
        question, targets = audit_extraordinary_question_service.get_question(question_id)
        self.assertEqual(question.question_text, "Uložená otázka")
        self.assertEqual(
            [int(item.workplace_id) for item in targets],
            [int(self.workplace.id)],
        )
        self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        dialog = self._open()
        self._fill(dialog, "Beze změny")
        first = self._run(dialog._save_btn.click)
        self.assertEqual(len(first), 1)
        second = self._run(dialog._save_btn.click)
        self.assertEqual(second, [])
        self.assertEqual(dialog.question_text.toPlainText(), "Beze změny")
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        dialog = self._open()
        self._fill(dialog, "Platná otázka")
        dialog.note.setPlainText("původní poznámka")
        self._run(dialog._save_btn.click)
        question_id = int(dialog.question_id)

        dialog.question_text.setPlainText("   ")
        dialog.note.setPlainText("rozepsaná poznámka")
        with patch(
            "moduly.audity.ui.extraordinary_question_editor_dialog.QMessageBox.warning"
        ) as warn:
            shown = self._run(dialog._save_btn.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn(EXTRAORDINARY_QUESTION_TEXT_REQUIRED, warn.call_args.args[2])
        self.assertEqual(dialog.question_text.toPlainText(), "   ")
        self.assertEqual(dialog.note.toPlainText(), "rozepsaná poznámka")
        self.assertTrue(dialog._is_dirty())
        question, _targets = audit_extraordinary_question_service.get_question(question_id)
        self.assertEqual(question.question_text, "Platná otázka")
        self.assertEqual(question.note, "původní poznámka")
        self._close(dialog)

    def test_other_save_actions_do_not_confirm(self) -> None:
        dialog = self._open()
        self._fill(dialog, "K zavření")
        shown = self._run(dialog._save_close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        question_id = int(dialog.question_id)

        clean = self._open(question_id)
        shown = self._run(clean._close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(clean.result(), QDialog.DialogCode.Rejected)

        dirty = self._open(question_id)
        dirty.note.setPlainText("z promptu zavření")
        with patch(
            "moduly.audity.ui.extraordinary_question_editor_dialog.confirm_unsaved_editor_close",
            return_value="save",
        ):
            shown = self._run(dirty._close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dirty.result(), QDialog.DialogCode.Accepted)
        question, _targets = audit_extraordinary_question_service.get_question(question_id)
        self.assertEqual(question.note, "z promptu zavření")
