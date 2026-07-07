from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog, create_save_cancel_box
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS, VALID_DOCUMENT_TYPES


class LegalDocumentDialog(QDialog):
    def __init__(self, parent=None, document=None):
        super().__init__(parent)
        self.document = document

        self.setWindowTitle("Právní předpis" if document is None else "Upravit právní předpis")
        configure_resizable_form_dialog(self, width=700, height=560, min_width=520, min_height=420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.document_type = QComboBox()
        for key in sorted(DOCUMENT_TYPE_LABELS, key=lambda item: DOCUMENT_TYPE_LABELS[item]):
            self.document_type.addItem(DOCUMENT_TYPE_LABELS[key], key)
        self.number = QLineEdit()
        self.year = QLineEdit()
        self.year.setPlaceholderText("Volitelné")
        self.title = QLineEdit()
        self.short_title = QLineEdit()
        self.valid_from = NullableDateEdit()
        self.valid_to = NullableDateEdit()
        self.effective_from = NullableDateEdit()
        self.effective_to = NullableDateEdit()
        self.source_url = QLineEdit()
        self.local_file_path = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        form.addRow("Typ předpisu:", self.document_type)
        form.addRow("Číslo:", self.number)
        form.addRow("Rok:", self.year)
        form.addRow("Název:", self.title)
        form.addRow("Zkratka:", self.short_title)
        form.addRow("Platnost od:", self.valid_from)
        form.addRow("Platnost do:", self.valid_to)
        form.addRow("Účinnost od:", self.effective_from)
        form.addRow("Účinnost do:", self.effective_to)
        form.addRow("Zdroj URL:", self.source_url)
        form.addRow("Lokální soubor:", self.local_file_path)
        form.addRow("Poznámka:", self.note)

        layout.addLayout(form)
        layout.addWidget(create_save_cancel_box(self))

        if document is not None:
            self._load_document(document)

    def _load_document(self, document) -> None:
        index = self.document_type.findData(document.document_type)
        self.document_type.setCurrentIndex(index if index >= 0 else 0)
        self.number.setText(document.number)
        if document.year is not None:
            self.year.setText(str(document.year))
        self.title.setText(document.title)
        self.short_title.setText(document.short_title)
        self.valid_from.set_date_value(document.valid_from)
        self.valid_to.set_date_value(document.valid_to)
        self.effective_from.set_date_value(document.effective_from)
        self.effective_to.set_date_value(document.effective_to)
        self.source_url.setText(document.source_url)
        self.local_file_path.setText(document.local_file_path)
        self.note.setPlainText(document.note)

    def get_data(self) -> dict:
        document_type = self.document_type.currentData() or ""
        year_text = self.year.text().strip()
        year = int(year_text) if year_text else None

        return {
            "document_type": document_type,
            "number": self.number.text().strip(),
            "year": year,
            "title": self.title.text().strip(),
            "short_title": self.short_title.text().strip(),
            "valid_from": self.valid_from.get_date(),
            "valid_to": self.valid_to.get_date(),
            "effective_from": self.effective_from.get_date(),
            "effective_to": self.effective_to.get_date(),
            "source_url": self.source_url.text().strip(),
            "local_file_path": self.local_file_path.text().strip(),
            "note": self.note.toPlainText().strip(),
        }

    def accept(self) -> None:
        data = self.get_data()
        if data["document_type"] not in VALID_DOCUMENT_TYPES:
            QMessageBox.warning(self, "Právní předpis", "Vyberte typ předpisu.")
            return
        if not data["title"]:
            QMessageBox.warning(self, "Právní předpis", "Název je povinný.")
            return
        super().accept()
