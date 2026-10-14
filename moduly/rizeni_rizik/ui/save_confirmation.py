"""Potvrzení úspěšného uložení v katalogu rizik a kategoriích."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

_SAVE_CONFIRMATION_TITLE = "Řízení rizik"
_SAVE_CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


def _exec_message_box(box: QMessageBox) -> int:
    return int(box.exec())


def show_risk_management_save_confirmation(parent: QWidget) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(_SAVE_CONFIRMATION_TITLE)
    box.setText(_SAVE_CONFIRMATION_TEXT)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    ok_button = box.button(QMessageBox.StandardButton.Ok)
    if ok_button is not None:
        ok_button.setText("OK")
    _exec_message_box(box)
