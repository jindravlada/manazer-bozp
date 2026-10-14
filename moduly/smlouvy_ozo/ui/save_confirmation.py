"""Potvrzení úspěšného uložení ve Smlouvách OZO."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from core.widgets.editor_dialog_controller import EditorDialogController

_SAVE_CONFIRMATION_TITLE = "Smlouvy OZO"
_SAVE_CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


def _exec_message_box(box: QMessageBox) -> int:
    return int(box.exec())


def show_ozo_save_confirmation(parent: QWidget) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(_SAVE_CONFIRMATION_TITLE)
    box.setText(_SAVE_CONFIRMATION_TEXT)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    ok_button = box.button(QMessageBox.StandardButton.Ok)
    if ok_button is not None:
        ok_button.setText("OK")
    _exec_message_box(box)


class ConfirmingSaveController(EditorDialogController):
    """Stay-open Uložit: dialog jen po skutečné změně a úspěšném zápisu."""

    def _handle_save_clicked(self) -> None:
        if self._on_save is None:
            super()._handle_save_clicked()
            return
        had_changes = self.is_dirty()
        if not self._run_save():
            return
        if had_changes:
            show_ozo_save_confirmation(self._dialog)
