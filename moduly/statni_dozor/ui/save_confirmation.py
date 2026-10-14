"""Potvrzení úspěšného uložení ve Státním dozoru."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from core.widgets.editor_dialog_controller import EditorDialogController

_SAVE_CONFIRMATION_TITLE = "Státní dozor"
_SAVE_CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


def _exec_message_box(box: QMessageBox) -> int:
    return int(box.exec())


def show_state_supervision_save_confirmation(parent: QWidget) -> None:
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
        had_changes = self.is_dirty()
        if not self._run_save():
            return
        if had_changes:
            show_state_supervision_save_confirmation(self._dialog)
