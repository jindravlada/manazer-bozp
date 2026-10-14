"""UKOLY-ULOZENI-1 – potvrzení úspěšného uložení úkolu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="ukoly-ulozeni-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog

CONFIRMATION_TITLE = "Úkoly"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class UkolyUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.ukoly.ui.task_dialog._exec_message_box",
            side_effect=_exec,
        ):
            action()
        return shown

    def _open(self, task) -> TaskDialog:
        dialog = TaskDialog(task=task)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog: TaskDialog) -> None:
        dialog._closing = True
        dialog.close()

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        task = task_service.create_task(
            title="Původní text",
            due_date=date(2026, 10, 30),
            note="původní poznámka",
        )
        dialog = self._open(task)
        dialog.title_edit.setPlainText("Uložený text")
        dialog.note_edit.setPlainText("uložená poznámka")
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
        self.assertFalse(dialog.isHidden())
        task_id = dialog.task.id
        self._close(dialog)

        reopened = self._open(task_service.get_task_by_id(task_id))
        self.assertEqual(reopened.title_edit.toPlainText(), "Uložený text")
        self.assertEqual(reopened.note_edit.toPlainText(), "uložená poznámka")
        self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        task = task_service.create_task(
            title="Beze změny",
            due_date=date(2026, 10, 30),
        )
        dialog = self._open(task)
        dialog.title_edit.setPlainText("Jedna změna")
        first = self._run(dialog._save_btn.click)
        self.assertEqual(len(first), 1)
        second = self._run(dialog._save_btn.click)
        self.assertEqual(second, [])
        self.assertEqual(dialog.title_edit.toPlainText(), "Jedna změna")
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        task = task_service.create_task(
            title="Platný úkol",
            due_date=date(2026, 10, 1),
            note="původní poznámka",
        )
        dialog = self._open(task)
        dialog.note_edit.setPlainText("rozepsaná poznámka")
        dialog.remind_from_edit.set_date_value(date(2026, 11, 1))
        with patch("moduly.ukoly.ui.task_dialog.QMessageBox.warning") as warn:
            shown = self._run(dialog._save_btn.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn("Připomenout od", warn.call_args.args[2])
        self.assertEqual(dialog.note_edit.toPlainText(), "rozepsaná poznámka")
        self.assertEqual(dialog.remind_from_edit.get_date(), date(2026, 11, 1))
        self.assertTrue(dialog._is_dirty())
        stored = task_service.get_task_by_id(task.id)
        self.assertEqual(stored.note, "původní poznámka")
        self.assertIsNone(stored.remind_from)
        self._close(dialog)

    def test_save_and_close_does_not_confirm(self) -> None:
        task = task_service.create_task(
            title="K zavření",
            due_date=date(2026, 10, 30),
        )
        dialog = self._open(task)
        dialog.note_edit.setPlainText("uloženo zavřením")
        shown = self._run(dialog._save_close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = task_service.get_task_by_id(task.id)
        self.assertEqual(stored.note, "uloženo zavřením")

    def test_close_without_save_button_does_not_confirm(self) -> None:
        task = task_service.create_task(
            title="Zavřít",
            due_date=date(2026, 10, 30),
        )
        dialog = self._open(task)
        shown = self._run(dialog._close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

        dialog = self._open(task_service.get_task_by_id(task.id))
        dialog.title_edit.setPlainText("z promptu zavření")
        with patch(
            "moduly.ukoly.ui.task_dialog.confirm_unsaved_editor_close",
            return_value="save",
        ):
            shown = self._run(dialog._close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = task_service.get_task_by_id(task.id)
        self.assertEqual(stored.title, "z promptu zavření")
