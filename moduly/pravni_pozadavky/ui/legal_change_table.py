from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.pravni_pozadavky.constants import CHANGE_TYPE_LABELS


def _format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    return str(value)


class LegalChangeTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(9)
        self.setHorizontalHeaderLabels([
            "ID",
            "Datum zveřejnění",
            "Typ změny",
            "Předpis ID",
            "Verze ID",
            "Ustanovení ID",
            "Název",
            "Vyhodnoceno",
            "Aktivní",
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
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        for column in (1, 2, 3, 4, 5, 7, 8):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(1, 120)
        self.setColumnWidth(2, 150)
        self.setColumnWidth(3, 80)
        self.setColumnWidth(4, 70)
        self.setColumnWidth(5, 100)
        self.setColumnWidth(7, 90)
        self.setColumnWidth(8, 80)

    def load_changes(self, changes) -> None:
        self.setRowCount(len(changes))

        for row, change in enumerate(changes):
            change_type = CHANGE_TYPE_LABELS.get(change.change_type, change.change_type)
            self._set_item(row, 0, str(change.id))
            self._set_item(row, 1, _format_date(change.published_at))
            self._set_item(row, 2, change_type)
            self._set_item(row, 3, str(change.legal_document_id))
            self._set_item(
                row,
                4,
                str(change.legal_document_version_id)
                if change.legal_document_version_id is not None
                else "",
            )
            self._set_item(
                row,
                5,
                str(change.legal_section_id) if change.legal_section_id is not None else "",
            )
            self._set_item(row, 6, change.title)
            self._set_item(row, 7, "Ano" if change.evaluated else "Ne")
            self._set_item(row, 8, "Ano" if change.active else "Ne")

            if not change.active:
                brush = QBrush(QColor("#f0f0f0"))
                for column in range(self.columnCount()):
                    item = self.item(row, column)
                    if item is not None:
                        item.setBackground(brush)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)

    def selected_change_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
