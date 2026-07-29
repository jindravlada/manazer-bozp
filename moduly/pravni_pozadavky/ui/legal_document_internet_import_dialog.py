from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
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
from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
    LegalDocumentJsonImportResult,
)
from moduly.pravni_pozadavky.import_export.legal_document_internet_import_service import (
    legal_document_internet_import_service,
)


class LegalDocumentInternetImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.import_result: LegalDocumentJsonImportResult | None = None

        self.setWindowTitle("Import právního předpisu z internetu")
        configure_resizable_form_dialog(self, width=520, height=300, min_width=420, min_height=240)

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

        self.type_hint = QLabel("Typ předpisu se určí automaticky podle údajů z e-Sbírky.")
        self.type_hint.setWordWrap(True)

        self.number = QLineEdit()
        self.year = QLineEdit()

        form.addRow("Typ předpisu:", self.type_hint)
        form.addRow("Číslo:", self.number)
        form.addRow("Rok:", self.year)
        return form_widget

    def get_data(self) -> dict:
        year_text = self.year.text().strip()
        year = int(year_text) if year_text else None
        return {
            "number": self.number.text().strip(),
            "year": year,
        }

    def _set_import_in_progress(self, active: bool) -> None:
        self.number.setEnabled(not active)
        self.year.setEnabled(not active)
        self.button_box.setEnabled(not active)
        if not active:
            self.status_label.hide()
            self.status_label.clear()

    def _update_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.show()
        QApplication.processEvents()

    def accept(self) -> None:
        data = self.get_data()
        if not data["number"]:
            QMessageBox.warning(self, "Import Internet", "Číslo předpisu je povinné.")
            return
        if data["year"] is None:
            QMessageBox.warning(self, "Import Internet", "Rok předpisu je povinný.")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self._set_import_in_progress(True)

        try:
            self.import_result = legal_document_internet_import_service.import_from_internet(
                number=data["number"],
                year=data["year"],
                on_status=self._update_status,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Import Internet", str(exc))
            return
        finally:
            self._set_import_in_progress(False)
            QApplication.restoreOverrideCursor()

        super().accept()
