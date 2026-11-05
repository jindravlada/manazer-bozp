from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
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
    typed_text,
)
from moduly.rizeni_rizik.constants import (
    SUPPLIER_RISK_COL_COMPANY,
    SUPPLIER_RISK_COL_ICO,
    SUPPLIER_RISK_COLUMN_COUNT,
    SUPPLIER_RISK_TABLE_HEADERS,
)
from moduly.rizeni_rizik.modely.supplier_risk import SupplierRiskCompany
from moduly.rizeni_rizik.sluzby.supplier_risk_service import (
    supplier_risk_search_matches,
    supplier_risk_service,
)
from moduly.rizeni_rizik.ui.supplier_risk_company_dialog import SupplierRiskCompanyDialog

_COMPANY_ID_ROLE = Qt.ItemDataRole.UserRole


class SupplierRiskDocumentsTab(QWidget):
    """Seznam dodavatelů. Jeden řádek je jedna firma, bez ohledu na počet dokumentů."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nový dodavatel")
        self.open_btn = QPushButton("Otevřít")
        self.new_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder)
        )
        self.open_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        self.open_btn.setEnabled(False)
        toolbar.addWidget(self.new_btn)
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

        self.new_btn.clicked.connect(lambda _checked=False: self.create_company())
        self.open_btn.clicked.connect(lambda _checked=False: self.open_company())
        self.table.doubleClicked.connect(lambda _index: self.open_company())
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
        configure_table_columns(table, "supplier_risk_companies")
        header = table.horizontalHeader()
        header.setSectionResizeMode(
            SUPPLIER_RISK_COL_COMPANY,
            QHeaderView.ResizeMode.Stretch,
        )
        table.setColumnWidth(SUPPLIER_RISK_COL_ICO, 140)
        return table

    def refresh(self) -> None:
        companies = supplier_risk_service.list_companies()
        with sorting_paused(self.table):
            self.table.setRowCount(len(companies))
            for index, company in enumerate(companies):
                self._set_row(index, company)
        self.text_filter.update_count()
        self._refresh_buttons()

    def _set_row(self, index: int, company: SupplierRiskCompany) -> None:
        name = create_typed_item(company.name, typed_text(company.name))
        name.setData(_COMPANY_ID_ROLE, company.id)
        ico_value = company.ico or ""
        ico = create_typed_item(ico_value or "—", typed_text(ico_value))
        self.table.setItem(index, SUPPLIER_RISK_COL_COMPANY, name)
        self.table.setItem(index, SUPPLIER_RISK_COL_ICO, ico)
        for item in (name, ico):
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

    def _selected_company_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.table.item(selected[0].row(), SUPPLIER_RISK_COL_COMPANY)
        if item is None:
            return None
        value = item.data(_COMPANY_ID_ROLE)
        return int(value) if value else None

    def _refresh_buttons(self) -> None:
        self.open_btn.setEnabled(self._selected_company_id() is not None)

    def create_company(self) -> None:
        dialog = SupplierRiskCompanyDialog(self)
        dialog.exec()
        self.refresh()

    def open_company(self) -> None:
        company_id = self._selected_company_id()
        if company_id is None:
            return
        company = supplier_risk_service.get_company(company_id)
        if company is None:
            self.refresh()
            return
        dialog = SupplierRiskCompanyDialog(self, company)
        dialog.exec()
        self.refresh()
