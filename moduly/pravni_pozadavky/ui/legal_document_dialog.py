from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    add_save_cancel_footer,
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS, VALID_DOCUMENT_TYPES
from moduly.pravni_pozadavky.ui.legal_document_versions_tab import LegalDocumentVersionsTab
from moduly.pravni_pozadavky.ui.legal_document_process_usage_tab import LegalDocumentProcessUsageTab
from moduly.pravni_pozadavky.ui.legal_document_hazard_catalog_sources_tab import (
    LegalDocumentHazardCatalogSourcesTab,
)

class LegalDocumentDialog(QDialog):
    def __init__(self, parent=None, document=None):
        super().__init__(parent)
        self.document = document

        self.setWindowTitle("Právní předpis" if document is None else "Upravit právní předpis")
        configure_resizable_form_dialog(self, width=720, height=620, min_width=520, min_height=460)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._main_tab()), "Předpis")
        self.versions_tab = LegalDocumentVersionsTab(
            document.id if document is not None else None,
        )
        self.tabs.addTab(wrap_in_scroll_area(self.versions_tab), "Verze")
        if document is not None:
            self.process_usage_tab = LegalDocumentProcessUsageTab(document_id=document.id)
            self.tabs.addTab(wrap_in_scroll_area(self.process_usage_tab), "Použití v procesech")
            self.hazard_sources_tab = LegalDocumentHazardCatalogSourcesTab(
                document_id=document.id,
            )
            self.tabs.addTab(
                wrap_in_scroll_area(self.hazard_sources_tab),
                "Zdroje rizik",
            )
        layout.addWidget(self.tabs, 1)
        add_save_cancel_footer(layout, self, is_new=document is None)

        if document is not None:
            self._load_document(document)

    def _main_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

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
        self.included_in_processes = QComboBox()
        self.included_in_processes.addItem("NE", False)
        self.included_in_processes.addItem("ANO", True)

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
        form.addRow("Zahrnuto v procesech:", self.included_in_processes)
        form.addRow("Poznámka:", self.note)
        return tab

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
        included_index = self.included_in_processes.findData(document.included_in_processes)
        self.included_in_processes.setCurrentIndex(included_index if included_index >= 0 else 0)

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
            "included_in_processes": bool(self.included_in_processes.currentData()),
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
