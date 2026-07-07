from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog, create_save_cancel_box
from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS, VALID_DOCUMENT_TYPES


class LegalDocumentTxtImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import právního předpisu z TXT")
        configure_resizable_form_dialog(self, width=520, height=320, min_width=420, min_height=260)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_form())
        layout.addWidget(create_save_cancel_box(self))

    def _build_form(self) -> QWidget:
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self.document_type = QComboBox()
        self.document_type.addItem("— vyberte —", "")
        for key in sorted(DOCUMENT_TYPE_LABELS, key=lambda item: DOCUMENT_TYPE_LABELS[item]):
            self.document_type.addItem(DOCUMENT_TYPE_LABELS[key], key)

        self.number = QLineEdit()
        self.year = QLineEdit()
        self.year.setPlaceholderText("Volitelné")
        self.title = QLineEdit()
        self.short_title = QLineEdit()

        form.addRow("Typ předpisu:", self.document_type)
        form.addRow("Číslo:", self.number)
        form.addRow("Rok:", self.year)
        form.addRow("Název:", self.title)
        form.addRow("Zkratka:", self.short_title)
        return form_widget

    def get_data(self) -> dict:
        year_text = self.year.text().strip()
        year = int(year_text) if year_text else None
        return {
            "document_type": self.document_type.currentData() or "",
            "number": self.number.text().strip(),
            "year": year,
            "title": self.title.text().strip(),
            "short_title": self.short_title.text().strip(),
        }

    def accept(self) -> None:
        data = self.get_data()
        if data["document_type"] not in VALID_DOCUMENT_TYPES:
            QMessageBox.warning(self, "Import TXT", "Typ předpisu je povinný.")
            return
        if not data["title"]:
            QMessageBox.warning(self, "Import TXT", "Název je povinný.")
            return
        super().accept()
