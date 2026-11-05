from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QStyle,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.filter_bar import FilterBar
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
    SUPPLIER_RISK_COL_COMPANY,
    SUPPLIER_RISK_COL_DATE,
    SUPPLIER_RISK_COL_DOCUMENT,
    SUPPLIER_RISK_COL_ICO,
    SUPPLIER_RISK_COL_NOTE,
    SUPPLIER_RISK_COLUMN_COUNT,
    SUPPLIER_RISK_TABLE_HEADERS,
)
from moduly.rizeni_rizik.sluzby.supplier_risk_service import (
    SupplierRiskDocumentRow,
    SupplierRiskError,
    supplier_risk_search_matches,
    supplier_risk_service,
)
from moduly.rizeni_rizik.ui.supplier_risk_document_dialog import (
    SupplierRiskDocumentDialog,
)

_DOCUMENT_ID_ROLE = Qt.ItemDataRole.UserRole


class SupplierRiskDocumentsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nový záznam")
        self.edit_btn = QPushButton("Upravit záznam")
        self.open_btn = QPushButton("Otevřít dokument")
        self.new_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder)
        )
        self.edit_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self.open_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        self.edit_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = self._build_table()
        self.text_filter = FilterBar(
            self.table,
            apply_fn=self._apply_search,
        )
        self.text_filter.search_edit.setPlaceholderText(
            "🔍 Hledat podle názvu firmy nebo IČO..."
        )
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(lambda _checked=False: self.create_document())
        self.edit_btn.clicked.connect(lambda _checked=False: self.edit_document())
        self.open_btn.clicked.connect(lambda _checked=False: self.open_document())
        self.table.doubleClicked.connect(lambda _index: self.edit_document())
        self.table.itemSelectionChanged.connect(self._refresh_buttons)
        self.refresh()

    def _build_table(self):
        table = QTableWidget(0, SUPPLIER_RISK_COLUMN_COUNT)
        table.setHorizontalHeaderLabels(SUPPLIER_RISK_TABLE_HEADERS)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.verticalHeader().setVisible(False)
        enable_typed_sorting(table)
        configure_table_columns(table, "supplier_risk_documents")
        header = table.horizontalHeader()
        header.setSectionResizeMode(
            SUPPLIER_RISK_COL_COMPANY,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            SUPPLIER_RISK_COL_DOCUMENT,
            QHeaderView.ResizeMode.Stretch,
        )
        table.setColumnWidth(SUPPLIER_RISK_COL_ICO, 110)
        table.setColumnWidth(SUPPLIER_RISK_COL_DATE, 130)
        table.setColumnWidth(SUPPLIER_RISK_COL_NOTE, 220)
        return table

    def refresh(self) -> None:
        rows = supplier_risk_service.list_documents()
        with sorting_paused(self.table):
            self.table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                self._set_row(index, row)
        self.text_filter.update_count()
        self._refresh_buttons()

    def _set_row(self, index: int, row: SupplierRiskDocumentRow) -> None:
        company = create_typed_item(row.company_name, typed_text(row.company_name))
        company.setData(_DOCUMENT_ID_ROLE, row.id)
        ico = create_typed_item(row.ico or "—", typed_text(row.ico))
        document = create_typed_item(row.filename, typed_text(row.filename))
        if row.received_on is None:
            received = create_typed_item("—", typed_empty())
        else:
            received = create_typed_item(
                row.received_on.strftime("%d.%m.%Y"),
                typed_date(row.received_on),
            )
        note = create_typed_item(row.note, typed_text(row.note))
        self.table.setItem(index, SUPPLIER_RISK_COL_COMPANY, company)
        self.table.setItem(index, SUPPLIER_RISK_COL_ICO, ico)
        self.table.setItem(index, SUPPLIER_RISK_COL_DOCUMENT, document)
        self.table.setItem(index, SUPPLIER_RISK_COL_DATE, received)
        self.table.setItem(index, SUPPLIER_RISK_COL_NOTE, note)
        for item in (company, ico, document, received, note):
            apply_cell_tooltip(item, item.text())

    def _apply_search(self, text: str) -> tuple[int, int]:
        total = self.table.rowCount()
        visible = 0
        for row in range(total):
            company = self.table.item(row, SUPPLIER_RISK_COL_COMPANY)
            ico = self.table.item(row, SUPPLIER_RISK_COL_ICO)
            company_text = "" if company is None else company.text()
            ico_text = "" if ico is None else ico.text()
            if ico_text == "—":
                ico_text = ""
            match = supplier_risk_search_matches(
                company_name=company_text,
                ico=ico_text,
                query=text,
            )
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1
        return visible, total

    def _selected_document_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.table.item(selected[0].row(), SUPPLIER_RISK_COL_COMPANY)
        if item is None:
            return None
        value = item.data(_DOCUMENT_ID_ROLE)
        return int(value) if value else None

    def _refresh_buttons(self) -> None:
        enabled = self._selected_document_id() is not None
        self.edit_btn.setEnabled(enabled)
        self.open_btn.setEnabled(enabled)

    def create_document(self) -> None:
        dialog = SupplierRiskDocumentDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.refresh()

    def edit_document(self) -> None:
        document_id = self._selected_document_id()
        if document_id is None:
            return
        document = self._row(document_id)
        if document is None:
            return
        dialog = SupplierRiskDocumentDialog(self, document)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.refresh()

    def open_document(self) -> None:
        document_id = self._selected_document_id()
        if document_id is None:
            return
        try:
            supplier_risk_service.open_document(document_id, parent=self)
        except SupplierRiskError as exc:
            QMessageBox.warning(self, "Dokument rizik", str(exc))

    def _row(self, document_id: int) -> SupplierRiskDocumentRow | None:
        for row in supplier_risk_service.list_documents():
            if row.id == document_id:
                return row
        return None
