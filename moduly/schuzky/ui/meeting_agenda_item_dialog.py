"""Editor bodu jednání – karta tématu."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.schuzky.constants import AGENDA_ITEM_DIALOG_TITLE


def _plain_text_edit(*, placeholder: str, min_height: int) -> QTextEdit:
    edit = QTextEdit()
    edit.setPlaceholderText(placeholder)
    edit.setAcceptRichText(False)
    edit.setMinimumHeight(min_height)
    return edit


class MeetingAgendaItemDialog(QDialog):
    def __init__(self, parent=None, *, item: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(AGENDA_ITEM_DIALOG_TITLE)
        self.resize(560, 520)

        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Název tématu")

        # Běžné / rozsáhlé / běžné podle UI_KOMPONENTY.md
        self.moje_sdeleni_edit = _plain_text_edit(
            placeholder="Moje sdělení",
            min_height=110,
        )
        self.prubeh_jednani_edit = _plain_text_edit(
            placeholder="Průběh jednání",
            min_height=150,
        )
        self.zaver_edit = _plain_text_edit(
            placeholder="Závěr",
            min_height=110,
        )

        form.addRow("Název tématu:", self.title_edit)
        form.addRow("Moje sdělení:", self.moje_sdeleni_edit)
        form.addRow("Průběh jednání:", self.prubeh_jednani_edit)
        form.addRow("Závěr:", self.zaver_edit)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        buttons = create_save_cancel_box(self, is_new=item is None)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if item is not None:
            self.title_edit.setText(item.get("title") or "")
            self.moje_sdeleni_edit.setPlainText(item.get("moje_sdeleni") or "")
            self.prubeh_jednani_edit.setPlainText(item.get("prubeh_jednani") or "")
            self.zaver_edit.setPlainText(item.get("zaver") or "")

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "moje_sdeleni": self.moje_sdeleni_edit.toPlainText(),
            "prubeh_jednani": self.prubeh_jednani_edit.toPlainText(),
            "zaver": self.zaver_edit.toPlainText(),
        }
