from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    add_save_cancel_footer,
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS, VALID_DOCUMENT_TYPES
from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
    LegalDocumentJsonImportResult,
)
from moduly.pravni_pozadavky.import_export.legal_document_txt_import_service import (
    legal_document_txt_import_service,
)


class LegalDocumentTxtImportDialog(QDialog):
    def __init__(self, parent=None, *, file_path: str):
        super().__init__(parent)
        self.file_path = file_path
        self.import_result: LegalDocumentJsonImportResult | None = None

        self.setWindowTitle("Import právního předpisu z TXT")
        configure_resizable_form_dialog(self, width=520, height=340, min_width=420, min_height=280)

        layout = QVBoxLayout(self)
        layout.addWidget(wrap_in_scroll_area(self._build_form()), 1)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)
        self.button_box = add_save_cancel_footer(layout, self)

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

    def _set_import_in_progress(self, active: bool) -> None:
        self.document_type.setEnabled(not active)
        self.number.setEnabled(not active)
        self.year.setEnabled(not active)
        self.title.setEnabled(not active)
        self.short_title.setEnabled(not active)
        self.button_box.setEnabled(not active)
        if active:
            self.status_label.setText("Probíhá import…")
            self.status_label.show()
        else:
            self.status_label.hide()
            self.status_label.clear()

    def accept(self) -> None:
        data = self.get_data()
        if data["document_type"] not in VALID_DOCUMENT_TYPES:
            QMessageBox.warning(self, "Import TXT", "Typ předpisu je povinný.")
            return
        if not data["title"]:
            QMessageBox.warning(self, "Import TXT", "Název je povinný.")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self._set_import_in_progress(True)
        QApplication.processEvents()

        try:
            self.import_result = legal_document_txt_import_service.import_from_txt(
                self.file_path,
                **data,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Import TXT", str(exc))
            return
        finally:
            self._set_import_in_progress(False)
            QApplication.restoreOverrideCursor()

        super().accept()
