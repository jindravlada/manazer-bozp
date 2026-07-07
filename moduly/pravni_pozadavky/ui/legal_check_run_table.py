from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.pravni_pozadavky.constants import CHECK_RUN_STATUS_LABELS


def _format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    return str(value)


class LegalCheckRunTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "ID",
            "Název",
            "Období od",
            "Období do",
            "Datum kontroly",
            "Stav",
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
        for column in (2, 3, 4, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(3, 100)
        self.setColumnWidth(4, 120)
        self.setColumnWidth(5, 110)
        self.setColumnWidth(6, 80)

    def load_runs(self, runs) -> None:
        self.setRowCount(len(runs))

        for row, run in enumerate(runs):
            status = CHECK_RUN_STATUS_LABELS.get(run.status, run.status)
            self._set_item(row, 0, str(run.id))
            self._set_item(row, 1, run.title)
            self._set_item(row, 2, _format_date(run.period_from))
            self._set_item(row, 3, _format_date(run.period_to))
            self._set_item(row, 4, _format_date(run.checked_at))
            self._set_item(row, 5, status)
            self._set_item(row, 6, "Ano" if run.active else "Ne")

            if not run.active:
                brush = QBrush(QColor("#f0f0f0"))
                for column in range(self.columnCount()):
                    item = self.item(row, column)
                    if item is not None:
                        item.setBackground(brush)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)

    def selected_run_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
