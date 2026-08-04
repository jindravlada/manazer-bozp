"""Editor bodu jednání – zatím jen název tématu."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QVBoxLayout

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.schuzky.constants import AGENDA_ITEM_DIALOG_TITLE


class MeetingAgendaItemDialog(QDialog):
    def __init__(self, parent=None, *, item: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(AGENDA_ITEM_DIALOG_TITLE)
        self.resize(480, 160)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Název tématu")
        form.addRow("Název tématu:", self.title_edit)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self, is_new=item is None)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if item is not None:
            self.title_edit.setText(item.get("title") or "")

    def get_data(self) -> dict:
        return {"title": self.title_edit.text().strip()}
