"""UX-DIALOG-2 – jednotná logika tlačítek editorů."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.editor_dialog_controller import (
    EDITOR_CANCEL_LABEL,
    EDITOR_CLOSE_LABEL,
    EDITOR_SAVE_LABEL,
    EDITOR_UNSAVED_DISCARD_LABEL,
    EDITOR_UNSAVED_PROMPT,
    EDITOR_UNSAVED_SAVE_LABEL,
    EditorDialogController,
    confirm_unsaved_editor_close,
    create_editor_button_box,
)


class _SampleEditor(QDialog):
    def __init__(self, *, is_new: bool = True):
        super().__init__()
        self.setWindowTitle("Test editor")
        self._saved = False
        self._value = ""
        layout = QVBoxLayout(self)
        self.edit = QLineEdit()
        layout.addWidget(self.edit)
        self.buttons = create_editor_button_box(self, is_new=is_new)
        layout.addWidget(self.buttons)
        self.controller = EditorDialogController(
            self,
            self.buttons,
            is_new=is_new,
            title="Test editor",
            on_save=self._save,
            is_dirty=lambda: self.edit.text() != self._value,
        )
        if not is_new:
            self._value = "původní"
            self.edit.setText("původní")
            self.controller.capture_baseline()
        self.controller.install_auto_dirty_tracking(self.edit)

    def _save(self) -> bool:
        self._value = self.edit.text()
        self._saved = True
        return True


class UxDialog2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_new_record_shows_cancel_and_save(self) -> None:
        box = create_save_cancel_box(is_new=True)
        cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
        save = box.button(QDialogButtonBox.StandardButton.Save)
        self.assertEqual(cancel.text(), EDITOR_CANCEL_LABEL)
        self.assertEqual(save.text(), EDITOR_SAVE_LABEL)

    def test_existing_record_shows_close_and_save(self) -> None:
        box = create_save_cancel_box(is_new=False)
        cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
        self.assertEqual(cancel.text(), EDITOR_CLOSE_LABEL)

    def test_after_first_save_cancel_becomes_close(self) -> None:
        dialog = _SampleEditor(is_new=True)
        cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.assertEqual(cancel.text(), EDITOR_CANCEL_LABEL)
        dialog.edit.setText("nový")
        self.assertTrue(dialog.controller._run_save())
        self.assertEqual(cancel.text(), EDITOR_CLOSE_LABEL)
        self.assertFalse(dialog.controller.is_new)

    def test_existing_save_disabled_when_clean(self) -> None:
        dialog = _SampleEditor(is_new=False)
        save = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.assertFalse(save.isEnabled())
        dialog.edit.setText("změna")
        dialog.controller.mark_dirty()
        self.assertTrue(save.isEnabled())
        self.assertTrue(dialog.controller._run_save())
        self.assertFalse(save.isEnabled())

    def test_close_without_dirty_skips_prompt(self) -> None:
        dialog = _SampleEditor(is_new=False)
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close"
        ) as prompt:
            self.assertTrue(dialog.controller.request_close())
            prompt.assert_not_called()

    def test_close_with_dirty_shows_standard_prompt(self) -> None:
        dialog = _SampleEditor(is_new=False)
        dialog.edit.setText("změna")
        dialog.controller.mark_dirty()
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ) as prompt:
            self.assertFalse(dialog.controller.request_close())
            prompt.assert_called_once()
            self.assertEqual(prompt.call_args.kwargs.get("title"), "Test editor")

    def test_unsaved_prompt_labels(self) -> None:
        with patch("core.widgets.editor_dialog_controller.QMessageBox") as mock_box_cls:
            instance = mock_box_cls.return_value
            instance.clickedButton.return_value = None
            instance.exec.return_value = 0
            confirm_unsaved_editor_close(None, title="Editor")
            instance.setText.assert_called_once_with(EDITOR_UNSAVED_PROMPT)
            labels = [call.args[0] for call in instance.addButton.call_args_list]
            self.assertEqual(
                labels,
                [
                    EDITOR_UNSAVED_SAVE_LABEL,
                    EDITOR_UNSAVED_DISCARD_LABEL,
                    EDITOR_CANCEL_LABEL,
                ],
            )


if __name__ == "__main__":
    unittest.main()
