"""Odůvodnění stavu Nevykoná se u jednoho výskytu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QVBoxLayout, QMessageBox

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.periodicke_cinnosti.constants import CALENDAR_SKIP_REASON_REQUIRED
from moduly.rocni_plan.constants import SKIP_DIALOG_TITLE


class PeriodicSkipDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(SKIP_DIALOG_TITLE)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(460, 220)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Odůvodnění je povinné a platí jen pro vybraný výskyt."))
        self.reason_edit = QPlainTextEdit()
        self.reason_edit.setPlaceholderText("Proč se tento výskyt nevykoná")
        layout.addWidget(self.reason_edit)

        buttons = create_save_cancel_box(self, is_new=False)
        buttons.accepted.connect(self._accept_reason)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def reason(self) -> str:
        return self.reason_edit.toPlainText().strip()

    def _accept_reason(self) -> None:
        if not self.reason():
            QMessageBox.warning(self, SKIP_DIALOG_TITLE, CALENDAR_SKIP_REASON_REQUIRED)
            return
        self.accept()
