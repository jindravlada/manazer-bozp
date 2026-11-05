"""Nabídka dokumentů z katalogu pro jednoho dodavatele v koordinaci."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from moduly.koordinace_bozp.sluzby.coordination_supplier_risk_link_service import (
    CoordinationSupplierRiskLinkError,
    coordination_supplier_risk_link_service,
)
from moduly.rizeni_rizik.sluzby.supplier_risk_service import (
    SUPPLIER_CATALOG_MATCH_ONE,
    SupplierRiskError,
    supplier_risk_service,
)

_DOCUMENT_ID_ROLE = Qt.ItemDataRole.UserRole
_LINKED_ROLE = Qt.ItemDataRole.UserRole + 1

_COL_DOCUMENT = 0
_COL_PREPARED = 1
_COL_RECEIVED = 2
_COL_USED = 3
_DATE_SAMPLE = "00.00.0000"
_USED_SAMPLE = "Ano"

_DIALOG_TITLE = "Dokumenty z katalogu"
_APPROVAL_TEXT = (
    "Dodavatel odsouhlasil použitelnost vybraných dokumentů pro tuto koordinaci."
)
_REMOVE_TEXT = (
    "Odebrat vazbu na vybrané dokumenty v této koordinaci? "
    "Dokumenty v katalogu zůstanou."
)


def _exec_message_box(box: QMessageBox) -> int:
    return int(box.exec())


def _fixed_column_width(table: QTableWidget, *texts: str) -> int:
    """Šířka pevného sloupce pro nejdelší z textů, včetně místa na záhlaví."""
    header = table.horizontalHeader()
    sort_mark = table.style().pixelMetric(
        QStyle.PixelMetric.PM_HeaderMarkSize,
        None,
        header,
    )
    advance = max(header.fontMetrics().horizontalAdvance(text) for text in texts)
    return advance + sort_mark + 28


def _configure_catalog_columns(table: QTableWidget) -> None:
    """Název dokumentu bere zbývající šířku. Data a Použito zůstanou jen tak široká, jak potřebují."""
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(_COL_DOCUMENT, QHeaderView.ResizeMode.Stretch)
    prepared = _fixed_column_width(table, "Datum zpracování", _DATE_SAMPLE)
    received = _fixed_column_width(table, "Datum převzetí", _DATE_SAMPLE)
    used = _fixed_column_width(table, "Použito", _USED_SAMPLE)
    header.setMinimumSectionSize(used)
    for column, width in (
        (_COL_PREPARED, prepared),
        (_COL_RECEIVED, received),
        (_COL_USED, used),
    ):
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(column, width)


def _show_date(value: date | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y")


class CoordinationCatalogDocumentsDialog(QDialog):
    """Výběr existujících dokumentů. Zavření bez potvrzení nic neuloží."""

    def __init__(self, coordination_employer_id: int, parent=None):
        super().__init__(parent)
        self.employer_id = coordination_employer_id
        self.setWindowTitle(_DIALOG_TITLE)
        self.resize(760, 460)

        layout = QVBoxLayout(self)
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Dokument", "Datum zpracování", "Datum převzetí", "Použito"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        _configure_catalog_columns(self.table)
        layout.addWidget(self.table)

        self.approval_checkbox = QCheckBox(_APPROVAL_TEXT)
        layout.addWidget(self.approval_checkbox)

        buttons = QHBoxLayout()
        self.open_button = QPushButton("Otevřít")
        self.use_button = QPushButton("Použít vybrané")
        self.remove_button = QPushButton("Odebrat vazbu")
        self.close_button = QPushButton("Zavřít")
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.use_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.doubleClicked.connect(self.open_selected)
        self.approval_checkbox.toggled.connect(self._update_buttons)
        self.open_button.clicked.connect(self.open_selected)
        self.use_button.clicked.connect(self.confirm_selected)
        self.remove_button.clicked.connect(self.remove_selected)
        self.close_button.clicked.connect(self.reject)

        self._load()

    def _load(self) -> None:
        offer = coordination_supplier_risk_link_service.offer_for_employer(
            self.employer_id
        )
        linked_ids = {
            item.document_id
            for item in coordination_supplier_risk_link_service.list_for_employer(
                self.employer_id
            )
        }
        self.table.setRowCount(0)
        if offer.status != SUPPLIER_CATALOG_MATCH_ONE:
            self.info_label.setText(
                "Katalog nelze podle IČO jednoznačně nabídnout."
            )
            self.approval_checkbox.setEnabled(False)
            self._update_buttons()
            return
        company_name = ""
        if offer.documents:
            company_name = offer.documents[0].company_name
        elif offer.company_id is not None:
            company = supplier_risk_service.get_company(offer.company_id)
            company_name = company.name if company is not None else ""
        self.info_label.setText(
            company_name or "Dokumenty dodavatele z katalogu"
        )
        self.approval_checkbox.setEnabled(True)
        self.table.setRowCount(len(offer.documents))
        for row_index, document in enumerate(offer.documents):
            linked = document.id in linked_ids
            name_item = QTableWidgetItem(document.filename or "dokument")
            name_item.setData(_DOCUMENT_ID_ROLE, document.id)
            name_item.setData(_LINKED_ROLE, linked)
            self.table.setItem(row_index, 0, name_item)
            self.table.setItem(
                row_index,
                1,
                QTableWidgetItem(_show_date(document.prepared_on)),
            )
            self.table.setItem(
                row_index,
                2,
                QTableWidgetItem(_show_date(document.received_on)),
            )
            self.table.setItem(
                row_index,
                3,
                QTableWidgetItem("Ano" if linked else ""),
            )
        self._update_buttons()

    def _selected_rows(self) -> list[int]:
        return sorted({index.row() for index in self.table.selectedIndexes()})

    def _document_id(self, row: int) -> int | None:
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(_DOCUMENT_ID_ROLE)
        return int(value) if isinstance(value, int) else None

    def _is_linked(self, row: int) -> bool:
        item = self.table.item(row, 0)
        return bool(item is not None and item.data(_LINKED_ROLE))

    def _update_buttons(self) -> None:
        rows = self._selected_rows()
        offer_available = self.approval_checkbox.isEnabled()
        self.open_button.setEnabled(offer_available and len(rows) == 1)
        self.use_button.setEnabled(
            offer_available
            and bool(rows)
            and self.approval_checkbox.isChecked()
        )
        self.remove_button.setEnabled(
            offer_available and any(self._is_linked(row) for row in rows)
        )

    def open_selected(self) -> None:
        rows = self._selected_rows()
        if len(rows) != 1:
            return
        document_id = self._document_id(rows[0])
        if document_id is None:
            return
        try:
            supplier_risk_service.open_document(document_id, parent=self)
        except SupplierRiskError as error:
            self._warn(str(error))

    def confirm_selected(self) -> None:
        """Uloží jen nově vybrané dokumenty a jen při zaškrtnutém odsouhlasení."""
        if not self.approval_checkbox.isChecked():
            return
        document_ids: list[int] = []
        for row in self._selected_rows():
            document_id = self._document_id(row)
            if document_id is None or self._is_linked(row):
                continue
            document_ids.append(document_id)
        if not document_ids:
            return
        try:
            coordination_supplier_risk_link_service.confirm_documents(
                self.employer_id,
                document_ids,
                supplier_approved=True,
            )
        except CoordinationSupplierRiskLinkError as error:
            self._warn(str(error))
            return
        self.approval_checkbox.setChecked(False)
        self._load()

    def remove_selected(self) -> None:
        document_ids: list[int] = []
        for row in self._selected_rows():
            document_id = self._document_id(row)
            if document_id is None or not self._is_linked(row):
                continue
            document_ids.append(document_id)
        if not document_ids:
            return
        if not self._confirm_remove():
            return
        coordination_supplier_risk_link_service.remove_documents(
            self.employer_id,
            document_ids,
        )
        self._load()

    def _confirm_remove(self) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(_DIALOG_TITLE)
        box.setText(_REMOVE_TEXT)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        yes_button = box.button(QMessageBox.StandardButton.Yes)
        if yes_button is not None:
            yes_button.setText("Odebrat")
        no_button = box.button(QMessageBox.StandardButton.No)
        if no_button is not None:
            no_button.setText("Zrušit")
        return _exec_message_box(box) == int(QMessageBox.StandardButton.Yes)

    def _warn(self, text: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(_DIALOG_TITLE)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        _exec_message_box(box)
