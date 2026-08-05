"""Dialog pro externího účastníka události (ne z číselníku Osoby/THP)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.schuzky.constants import (
    EXTERNAL_PARTICIPANT_DIALOG_TITLE,
    EXTERNAL_PARTICIPANT_NAME_REQUIRED,
)


class ExternalParticipantDialog(QDialog):
    def __init__(self, parent=None, *, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(EXTERNAL_PARTICIPANT_DIALOG_TITLE)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(420, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Jméno a příjmení")
        self.organization_edit = QLineEdit()
        self.organization_edit.setPlaceholderText("Organizace / společnost")
        self.function_edit = QLineEdit()
        self.function_edit.setPlaceholderText("Funkce")
        self.contact_edit = QLineEdit()
        self.contact_edit.setPlaceholderText("Telefon, e-mail…")
        self.note_edit = QTextEdit()
        self.note_edit.setAcceptRichText(False)
        self.note_edit.setPlaceholderText("Poznámka")
        self.note_edit.setMinimumHeight(70)

        form.addRow("Jméno a příjmení:", self.name_edit)
        form.addRow("Organizace / společnost:", self.organization_edit)
        form.addRow("Funkce:", self.function_edit)
        form.addRow("Kontakt:", self.contact_edit)
        form.addRow("Poznámka:", self.note_edit)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self, is_new=data is None)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if data:
            self._load(data)

    def _load(self, data: dict) -> None:
        self.name_edit.setText(str(data.get("full_name") or ""))
        self.organization_edit.setText(str(data.get("organization") or ""))
        self.function_edit.setText(str(data.get("function") or ""))
        self.contact_edit.setText(str(data.get("contact") or ""))
        self.note_edit.setPlainText(str(data.get("note") or ""))

    def get_data(self) -> dict:
        return {
            "full_name": self.name_edit.text().strip(),
            "organization": self.organization_edit.text().strip(),
            "function": self.function_edit.text().strip(),
            "contact": self.contact_edit.text().strip(),
            "note": self.note_edit.toPlainText().strip(),
        }

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, EXTERNAL_PARTICIPANT_DIALOG_TITLE, EXTERNAL_PARTICIPANT_NAME_REQUIRED)
            self.name_edit.setFocus()
            return
        self.accept()
