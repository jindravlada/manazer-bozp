from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS


def _format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


class LegalDocumentTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(8)
        self.setHorizontalHeaderLabels([
            "ID",
            "Typ",
            "Číslo",
            "Rok",
            "Název",
            "Zkratka",
            "Účinnost od",
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
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        for column in (1, 2, 3, 5, 6, 7):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(1, 130)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(3, 60)
        self.setColumnWidth(5, 120)
        self.setColumnWidth(6, 110)
        self.setColumnWidth(7, 80)

    def load_documents(self, documents) -> None:
        self.setRowCount(len(documents))

        for row, document in enumerate(documents):
            self._set_item(row, 0, str(document.id))
            self._set_item(
                row,
                1,
                DOCUMENT_TYPE_LABELS.get(document.document_type, document.document_type),
            )
            self._set_item(row, 2, document.number)
            self._set_item(row, 3, str(document.year) if document.year is not None else "")
            self._set_item(row, 4, document.title)
            self._set_item(row, 5, document.short_title)
            self._set_item(row, 6, _format_date(document.effective_from or document.valid_from))
            self._set_item(row, 7, "Ano" if document.active else "Ne")

            if not document.active:
                brush = QBrush(QColor("#f0f0f0"))
                for column in range(self.columnCount()):
                    item = self.item(row, column)
                    if item is not None:
                        item.setBackground(brush)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)

    def selected_document_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
