from decimal import Decimal

from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_empty,
    typed_float,
    typed_int,
    typed_text,
)


def _format_amount(value: Decimal | None, currency: str) -> str:
    if value is None:
        return ""
    amount = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    if currency:
        return f"{amount} {currency}"
    return amount


def _amount_sort_value(value: Decimal | None):
    if value is None:
        return typed_empty()
    return typed_float(float(value))


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

        enable_typed_sorting(self)

    def load_sanctions(self, sanctions) -> None:
        with sorting_paused(self):
            self.setRowCount(len(sanctions))

            for row, sanction in enumerate(sanctions):
                record_id = int(sanction.id)
                self.setItem(
                    row,
                    0,
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                )
                self.setItem(
                    row,
                    1,
                    create_typed_item(
                        sanction.authority,
                        typed_text(sanction.authority),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    2,
                    create_typed_item(
                        sanction.legal_reference,
                        typed_text(sanction.legal_reference),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    3,
                    create_typed_item(
                        sanction.description,
                        typed_text(sanction.description),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    4,
                    create_typed_item(
                        _format_amount(sanction.max_amount, sanction.currency),
                        _amount_sort_value(sanction.max_amount),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    5,
                    create_typed_item(
                        "Aktivní" if sanction.active else "Neaktivní",
                        typed_bool(sanction.active),
                        stable_id=record_id,
                    ),
                )

                if not sanction.active:
                    brush = QBrush(QColor("#f0f0f0"))
                    for column in range(self.columnCount()):
                        item = self.item(row, column)
                        if item is not None:
                            item.setBackground(brush)

    def selected_sanction_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
