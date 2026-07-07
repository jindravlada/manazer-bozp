from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem


def _format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


class LegalDocumentVersionTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(6)
        self.setHorizontalHeaderLabels([
            "ID",
            "Verze",
            "Účinnost od",
            "Účinnost do",
            "Publikováno",
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
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(2, 110)
        self.setColumnWidth(3, 110)
        self.setColumnWidth(4, 110)
        self.setColumnWidth(5, 80)

    def load_versions(self, versions) -> None:
        self.setRowCount(len(versions))

        for row, version in enumerate(versions):
            self._set_item(row, 0, str(version.id))
            self._set_item(row, 1, version.version_name)
            self._set_item(row, 2, _format_date(version.effective_from))
            self._set_item(row, 3, _format_date(version.effective_to))
            self._set_item(row, 4, _format_date(version.publication_date))
            self._set_item(row, 5, "Ano" if version.active else "Ne")

            if not version.active:
                brush = QBrush(QColor("#f0f0f0"))
                for column in range(self.columnCount()):
                    item = self.item(row, column)
                    if item is not None:
                        item.setBackground(brush)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)

    def selected_version_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
