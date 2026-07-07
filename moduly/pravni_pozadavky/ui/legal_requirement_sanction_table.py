from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem


def _format_amount(value: Decimal | None, currency: str) -> str:
    if value is None:
        return ""
    amount = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    if currency:
        return f"{amount} {currency}"
    return amount


class LegalRequirementSanctionTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(6)
        self.setHorizontalHeaderLabels([
            "ID",
            "Orgán",
            "Právní odkaz",
            "Popis",
            "Horní hranice",
            "Stav",
        ])

        self.setColumnHidden(0, True)
        self.setWordWrap(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        for column in (1, 2, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(1, 160)
        self.setColumnWidth(2, 180)
        self.setColumnWidth(4, 140)
        self.setColumnWidth(5, 90)

    def load_sanctions(self, sanctions) -> None:
        self.setRowCount(len(sanctions))

        for row, sanction in enumerate(sanctions):
            self._set_item(row, 0, str(sanction.id))
            self._set_item(row, 1, sanction.authority)
            self._set_item(row, 2, sanction.legal_reference)
            self._set_item(row, 3, sanction.description)
            self._set_item(
                row,
                4,
                _format_amount(sanction.max_amount, sanction.currency),
            )
            self._set_item(row, 5, "Aktivní" if sanction.active else "Neaktivní")

            if not sanction.active:
                brush = QBrush(QColor("#f0f0f0"))
                for column in range(self.columnCount()):
                    item = self.item(row, column)
                    if item is not None:
                        item.setBackground(brush)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)

    def selected_sanction_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
