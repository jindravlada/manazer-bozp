from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from core.widgets.editor_dialog_controller import configure_editor_save_button
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.rizeni_rizik.sluzby.supplier_risk_service import (
    SupplierRiskDocumentRow,
    SupplierRiskError,
    supplier_risk_service,
)


class SupplierRiskDocumentDialog(QDialog):
    """Založení nebo úprava dokumentu rizik dodavatele."""

    def __init__(
        self,
        parent=None,
        document: SupplierRiskDocumentRow | None = None,
        *,
        company_id: int | None = None,
    ):
        super().__init__(parent)
        self.document = document
        self.company_id = company_id
        self._company_scoped = company_id is not None
        self.source_path = ""
        self._filling = False
        self.reused_existing_company = False
        if self._company_scoped:
            self.setWindowTitle(
                "Upravit dokument" if document is not None else "Přidat dokument"
            )
        else:
            self.setWindowTitle(
                "Upravit dokument rizik" if document is not None else "Nový dokument rizik"
            )
        configure_resizable_form_dialog(
            self,
            width=560,
            height=460,
            min_width=480,
            min_height=400,
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.prepared_on = NullableDateEdit()
        self.received_on = NullableDateEdit()
        self.note = QPlainTextEdit()
        self.note.setFixedHeight(self.fontMetrics().lineSpacing() * 4 + 16)
        self.file_name = QLabel("Dokument není vybrán.")
        self.file_name.setWordWrap(True)
        self.file_button = QPushButton("Vybrat dokument…")
        self.file_button.clicked.connect(lambda _checked=False: self._choose_file())

        file_row = QHBoxLayout()
        file_row.addWidget(self.file_name, 1)
        file_row.addWidget(self.file_button)

        if not self._company_scoped:
            self.company = QComboBox()
            self.name = QLineEdit()
            self.ico = QLineEdit()
            self.ares_button = QPushButton("Načíst z ARES")
            self.ares_button.clicked.connect(lambda _checked=False: self._load_from_ares())
            ico_row = QHBoxLayout()
            ico_row.addWidget(self.ico, 1)
            ico_row.addWidget(self.ares_button)
            form.addRow("Firma:", self.company)
            form.addRow("Název firmy *:", self.name)
            form.addRow("IČO *:", ico_row)
        document_label = "Dokument rizik:" if document is not None else "Dokument rizik *:"
        form.addRow(document_label, file_row)
        form.addRow("Datum zpracování:", self.prepared_on)
        form.addRow("Datum převzetí:", self.received_on)
        form.addRow("Poznámka:", self.note)
        layout.addLayout(form)

        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton(
            "Uložit",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        configure_editor_save_button(self.save_button)
        cancel = buttons.addButton("Zrušit", QDialogButtonBox.ButtonRole.RejectRole)
        self.save_button.clicked.connect(lambda _checked=False: self._save())
        cancel.clicked.connect(self.reject)
        layout.addWidget(buttons)

        if not self._company_scoped:
            self.company.currentIndexChanged.connect(self._on_company_changed)
        self._load()

    def _load(self) -> None:
        if self._company_scoped:
            self._load_company_scoped()
            return
        self._filling = True
        self.company.clear()
        self.company.addItem("Nová firma", None)
        companies = supplier_risk_service.list_companies()
        selected = 0
        for company in companies:
            label = company.name
            if company.ico:
                label = f"{company.name} ({company.ico})"
            self.company.addItem(label, company.id)
            if self.document is not None and company.id == self.document.company_id:
                selected = self.company.count() - 1
        self.company.setCurrentIndex(selected)
        if self.document is None:
            self.name.clear()
            self.ico.clear()
            self.file_button.setEnabled(True)
        else:
            self.name.setText(self.document.company_name)
            self.ico.setText(self.document.ico)
            self.prepared_on.set_date_value(self.document.prepared_on)
            self.received_on.set_date_value(self.document.received_on)
            self.note.setPlainText(self.document.note)
            self.file_name.setText(self.document.filename or "Dokument")
            self.file_button.setEnabled(False)
            self.file_button.setToolTip(
                "Novou verzi dokumentu evidujte jako nový záznam."
            )
        self._filling = False

    def _load_company_scoped(self) -> None:
        if self.document is None:
            self.file_button.setEnabled(True)
            return
        self.prepared_on.set_date_value(self.document.prepared_on)
        self.received_on.set_date_value(self.document.received_on)
        self.note.setPlainText(self.document.note)
        self.file_name.setText(self.document.filename or "Dokument")
        self.file_button.setEnabled(False)
        self.file_button.setToolTip(
            "Novou verzi dokumentu evidujte jako nový záznam."
        )

    def _on_company_changed(self) -> None:
        if self._filling:
            return
        company_id = self.company.currentData()
        if company_id is None:
            self.name.clear()
            self.ico.clear()
            return
        for company in supplier_risk_service.list_companies():
            if company.id == company_id:
                self.name.setText(company.name)
                self.ico.setText(company.ico or "")
                return

    def _load_from_ares(self) -> None:
        try:
            name = supplier_risk_service.company_name_from_ares(self.ico.text())
        except SupplierRiskError as exc:
            QMessageBox.warning(self, "ARES", str(exc))
            return
        self.name.setText(name)

    def _choose_file(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Vybrat dokument rizik",
            "",
            "Všechny soubory (*.*)",
        )
        if not path:
            return
        self.source_path = path
        self.file_name.setText(Path(path).name)

    def _date_error(self) -> str | None:
        if self.prepared_on.line_edit.text().strip() and self.prepared_on.get_date() is None:
            return "Datum zpracování nemá platný formát."
        if self.received_on.line_edit.text().strip() and self.received_on.get_date() is None:
            return "Datum převzetí nemá platný formát."
        return None

    def _save(self) -> None:
        date_error = self._date_error()
        if date_error:
            QMessageBox.warning(self, "Dokument rizik", date_error)
            return
        try:
            if self._company_scoped:
                self._save_for_company()
                result = None
            elif self.document is None:
                result = supplier_risk_service.create_document(
                    company_id=self.company.currentData(),
                    name=self.name.text(),
                    ico=self.ico.text(),
                    received_on=self.received_on.get_date(),
                    note=self.note.toPlainText(),
                    source_path=self.source_path,
                    prepared_on=self.prepared_on.get_date(),
                )
            else:
                result = supplier_risk_service.update_document(
                    self.document.id,
                    company_id=self.company.currentData(),
                    name=self.name.text(),
                    ico=self.ico.text(),
                    received_on=self.received_on.get_date(),
                    note=self.note.toPlainText(),
                    prepared_on=self.prepared_on.get_date(),
                )
        except SupplierRiskError as exc:
            QMessageBox.warning(self, "Dokument rizik", str(exc))
            return
        if result is None:
            self.accept()
            return
        self.reused_existing_company = result.reused_existing_company
        if result.reused_existing_company:
            QMessageBox.information(
                self,
                "Dokument rizik",
                "Firma s tímto IČO už je evidována. Dokument byl přiřazen k existujícímu záznamu.",
            )
        self.accept()

    def _save_for_company(self) -> None:
        if self.company_id is None:
            raise SupplierRiskError("Firma nebyla nalezena.")
        if self.document is None:
            supplier_risk_service.add_company_document(
                self.company_id,
                received_on=self.received_on.get_date(),
                note=self.note.toPlainText(),
                source_path=self.source_path,
                prepared_on=self.prepared_on.get_date(),
            )
            return
        supplier_risk_service.update_document_details(
            self.document.id,
            received_on=self.received_on.get_date(),
            note=self.note.toPlainText(),
            prepared_on=self.prepared_on.get_date(),
        )
