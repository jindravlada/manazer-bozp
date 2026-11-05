from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QTableWidget,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from core.widgets.editor_dialog_controller import configure_editor_save_button
from core.widgets.table_utils import apply_cell_tooltip, configure_table_columns
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_text,
)
from moduly.rizeni_rizik.constants import (
    SUPPLIER_RISK_DOC_COL_DOCUMENT,
    SUPPLIER_RISK_DOC_COL_NOTE,
    SUPPLIER_RISK_DOC_COL_PREPARED,
    SUPPLIER_RISK_DOC_COL_RECEIVED,
    SUPPLIER_RISK_DOC_COLUMN_COUNT,
    SUPPLIER_RISK_DOC_TABLE_HEADERS,
)
from moduly.rizeni_rizik.modely.supplier_risk import SupplierRiskCompany
from moduly.rizeni_rizik.sluzby.supplier_risk_service import (
    SupplierRiskDocumentRow,
    SupplierRiskError,
    supplier_risk_service,
)
from moduly.rizeni_rizik.ui.supplier_risk_document_dialog import (
    SupplierRiskDocumentDialog,
)

_DOCUMENT_ID_ROLE = Qt.ItemDataRole.UserRole
_SAVE_CONFIRMATION_TITLE = "Dodavatel"
_SAVE_CONFIRMATION_TEXT = "Údaje dodavatele byly úspěšně uloženy."


def _exec_message_box(box: QMessageBox) -> int:
    return int(box.exec())


def _show_identity_save_confirmation(parent: QDialog) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(_SAVE_CONFIRMATION_TITLE)
    box.setText(_SAVE_CONFIRMATION_TEXT)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    ok_button = box.button(QMessageBox.StandardButton.Ok)
    if ok_button is not None:
        ok_button.setText("OK")
    _exec_message_box(box)


def _date_item(value):
    if value is None:
        return create_typed_item("—", typed_empty())
    return create_typed_item(value.strftime("%d.%m.%Y"), typed_date(value))


class SupplierRiskCompanyDialog(QDialog):
    """Údaje dodavatele a jeho dokumenty rizik."""

    def __init__(self, parent=None, company: SupplierRiskCompany | None = None):
        super().__init__(parent)
        self.company = company
        self.setWindowTitle("Dodavatel" if company is not None else "Nový dodavatel")
        configure_resizable_form_dialog(
            self,
            width=760,
            height=640,
            min_width=640,
            min_height=520,
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.ico = QLineEdit()
        self.ares_button = QPushButton("Načíst z ARES")
        self.ares_button.clicked.connect(lambda _checked=False: self._load_from_ares())
        ico_row = QHBoxLayout()
        ico_row.addWidget(self.ico, 1)
        ico_row.addWidget(self.ares_button)
        form.addRow("Název firmy *:", self.name)
        form.addRow("IČO *:", ico_row)
        layout.addLayout(form)

        identity_buttons = QDialogButtonBox()
        self.save_button = identity_buttons.addButton(
            "Uložit",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        configure_editor_save_button(self.save_button)
        self.save_button.clicked.connect(lambda _checked=False: self._save_identity())
        layout.addWidget(identity_buttons)

        layout.addWidget(QLabel("Dokumenty"))
        document_toolbar = QHBoxLayout()
        self.add_document_btn = QPushButton("Přidat dokument")
        self.edit_document_btn = QPushButton("Upravit dokument")
        self.open_document_btn = QPushButton("Otevřít dokument")
        self.add_document_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder)
        )
        self.edit_document_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self.open_document_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        document_toolbar.addWidget(self.add_document_btn)
        document_toolbar.addWidget(self.edit_document_btn)
        document_toolbar.addWidget(self.open_document_btn)
        document_toolbar.addStretch()
        layout.addLayout(document_toolbar)

        self.documents = self._build_documents_table()
        layout.addWidget(self.documents, 1)

        buttons = QDialogButtonBox()
        close_button = buttons.addButton("Zavřít", QDialogButtonBox.ButtonRole.RejectRole)
        close_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self.add_document_btn.clicked.connect(lambda _checked=False: self._add_document())
        self.edit_document_btn.clicked.connect(
            lambda _checked=False: self._edit_document()
        )
        self.open_document_btn.clicked.connect(
            lambda _checked=False: self._open_document()
        )
        self.documents.doubleClicked.connect(lambda _index: self._open_document())
        self.documents.itemSelectionChanged.connect(self._refresh_document_buttons)

        if company is not None:
            self.name.setText(company.name or "")
            self.ico.setText(company.ico or "")
        self._refresh_documents()

    def _build_documents_table(self) -> QTableWidget:
        table = QTableWidget(0, SUPPLIER_RISK_DOC_COLUMN_COUNT)
        table.setHorizontalHeaderLabels(SUPPLIER_RISK_DOC_TABLE_HEADERS)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.verticalHeader().setVisible(False)
        enable_typed_sorting(table)
        configure_table_columns(table, "supplier_risk_company_documents")
        header = table.horizontalHeader()
        header.setSectionResizeMode(
            SUPPLIER_RISK_DOC_COL_DOCUMENT,
            QHeaderView.ResizeMode.Stretch,
        )
        table.setColumnWidth(SUPPLIER_RISK_DOC_COL_PREPARED, 150)
        table.setColumnWidth(SUPPLIER_RISK_DOC_COL_RECEIVED, 140)
        table.setColumnWidth(SUPPLIER_RISK_DOC_COL_NOTE, 220)
        return table

    def _load_from_ares(self) -> None:
        try:
            name = supplier_risk_service.company_name_from_ares(self.ico.text())
        except SupplierRiskError as exc:
            QMessageBox.warning(self, "ARES", str(exc))
            return
        self.name.setText(name)

    def _save_identity(self) -> None:
        try:
            if self.company is None:
                saved = supplier_risk_service.create_company(
                    name=self.name.text(),
                    ico=self.ico.text(),
                )
            else:
                saved = supplier_risk_service.update_company_identity(
                    self.company.id,
                    name=self.name.text(),
                    ico=self.ico.text(),
                )
        except SupplierRiskError as exc:
            QMessageBox.warning(self, "Dodavatel", str(exc))
            return
        self.company = saved
        self.name.setText(saved.name or "")
        self.ico.setText(saved.ico or "")
        self.setWindowTitle("Dodavatel")
        self._refresh_document_buttons()
        _show_identity_save_confirmation(self)

    def _refresh_documents(self) -> None:
        rows: list[SupplierRiskDocumentRow] = []
        if self.company is not None:
            rows = supplier_risk_service.list_company_documents(self.company.id)
        with sorting_paused(self.documents):
            self.documents.setRowCount(len(rows))
            for index, row in enumerate(rows):
                self._set_document_row(index, row)
        self._refresh_document_buttons()

    def _set_document_row(self, index: int, row: SupplierRiskDocumentRow) -> None:
        document = create_typed_item(row.filename, typed_text(row.filename))
        document.setData(_DOCUMENT_ID_ROLE, row.id)
        prepared = _date_item(row.prepared_on)
        received = _date_item(row.received_on)
        note = create_typed_item(row.note, typed_text(row.note))
        self.documents.setItem(index, SUPPLIER_RISK_DOC_COL_DOCUMENT, document)
        self.documents.setItem(index, SUPPLIER_RISK_DOC_COL_PREPARED, prepared)
        self.documents.setItem(index, SUPPLIER_RISK_DOC_COL_RECEIVED, received)
        self.documents.setItem(index, SUPPLIER_RISK_DOC_COL_NOTE, note)
        for item in (document, prepared, received, note):
            apply_cell_tooltip(item, item.text())

    def _selected_document_id(self) -> int | None:
        selected = self.documents.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.documents.item(selected[0].row(), SUPPLIER_RISK_DOC_COL_DOCUMENT)
        if item is None:
            return None
        value = item.data(_DOCUMENT_ID_ROLE)
        return int(value) if value else None

    def _selected_document(self) -> SupplierRiskDocumentRow | None:
        document_id = self._selected_document_id()
        if document_id is None or self.company is None:
            return None
        for row in supplier_risk_service.list_company_documents(self.company.id):
            if row.id == document_id:
                return row
        return None

    def _refresh_document_buttons(self) -> None:
        has_company = self.company is not None
        has_document = self._selected_document_id() is not None
        self.add_document_btn.setEnabled(has_company)
        self.edit_document_btn.setEnabled(has_company and has_document)
        self.open_document_btn.setEnabled(has_company and has_document)
        if has_company:
            self.add_document_btn.setToolTip("")
        else:
            self.add_document_btn.setToolTip("Nejprve uložte název a IČO.")

    def _add_document(self) -> None:
        if self.company is None:
            return
        dialog = SupplierRiskDocumentDialog(self, company_id=self.company.id)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._refresh_documents()

    def _edit_document(self) -> None:
        document = self._selected_document()
        if document is None or self.company is None:
            return
        dialog = SupplierRiskDocumentDialog(
            self,
            document,
            company_id=self.company.id,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._refresh_documents()

    def _open_document(self) -> None:
        document_id = self._selected_document_id()
        if document_id is None:
            return
        try:
            supplier_risk_service.open_document(document_id, parent=self)
        except SupplierRiskError as exc:
            QMessageBox.warning(self, "Dokument rizik", str(exc))
