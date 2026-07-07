from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    add_save_cancel_footer,
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from moduly.pravni_pozadavky.constants import SECTION_TYPE_LABELS, VALID_SECTION_TYPES


class LegalSectionDialog(QDialog):
    def __init__(self, parent=None, section=None):
        super().__init__(parent)
        self.section = section

        self.setWindowTitle("Část předpisu" if section is None else "Upravit část předpisu")
        configure_resizable_form_dialog(self, width=680, height=560, min_width=520, min_height=420)

        layout = QVBoxLayout(self)
        content = QWidget()
        form = QFormLayout(content)

        self.section_type = QComboBox()
        for key in sorted(SECTION_TYPE_LABELS, key=lambda item: SECTION_TYPE_LABELS[item]):
            self.section_type.addItem(SECTION_TYPE_LABELS[key], key)
        self.parent_section_id = QLineEdit()
        self.parent_section_id.setPlaceholderText("Volitelné")
        self.section_number = QLineEdit()
        self.paragraph = QLineEdit()
        self.item_letter = QLineEdit()
        self.title = QLineEdit()
        self.text = QTextEdit()
        self.text.setMinimumHeight(120)
        self.sort_order = QLineEdit()
        self.sort_order.setText("0")
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        form.addRow("Typ části:", self.section_type)
        form.addRow("Nadřazená část ID:", self.parent_section_id)
        form.addRow("Číslo:", self.section_number)
        form.addRow("§:", self.paragraph)
        form.addRow("Písmeno:", self.item_letter)
        form.addRow("Název:", self.title)
        form.addRow("Text:", self.text)
        form.addRow("Pořadí:", self.sort_order)
        form.addRow("Poznámka:", self.note)

        layout.addWidget(wrap_in_scroll_area(content), 1)
        add_save_cancel_footer(layout, self)

        if section is not None:
            self._load_section(section)

    def _load_section(self, section) -> None:
        index = self.section_type.findData(section.section_type)
        self.section_type.setCurrentIndex(index if index >= 0 else 0)
        if section.parent_section_id is not None:
            self.parent_section_id.setText(str(section.parent_section_id))
        self.section_number.setText(section.section_number)
        self.paragraph.setText(section.paragraph)
        self.item_letter.setText(section.item_letter)
        self.title.setText(section.title)
        self.text.setPlainText(section.text)
        self.sort_order.setText(str(section.sort_order))
        self.note.setPlainText(section.note)

    def get_data(self) -> dict:
        parent_text = self.parent_section_id.text().strip()
        parent_section_id = int(parent_text) if parent_text else None
        sort_order_text = self.sort_order.text().strip()
        sort_order = int(sort_order_text) if sort_order_text else 0

        return {
            "section_type": self.section_type.currentData() or "",
            "parent_section_id": parent_section_id,
            "section_number": self.section_number.text().strip(),
            "paragraph": self.paragraph.text().strip(),
            "item_letter": self.item_letter.text().strip(),
            "title": self.title.text().strip(),
            "text": self.text.toPlainText().strip(),
            "sort_order": sort_order,
            "note": self.note.toPlainText().strip(),
        }

    def accept(self) -> None:
        data = self.get_data()
        if data["section_type"] not in VALID_SECTION_TYPES:
            QMessageBox.warning(self, "Část předpisu", "Vyberte typ části.")
            return
        if not data["section_number"] and not data["title"] and not data["text"]:
            QMessageBox.warning(
                self,
                "Část předpisu",
                "Vyplňte číslo, název nebo text části.",
            )
            return
        super().accept()
