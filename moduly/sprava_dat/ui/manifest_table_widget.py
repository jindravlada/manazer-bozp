from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)


class ManifestTableWidget(QTableWidget):
    """Read-only tabulka manifestu se sloupci Položka | Hodnota | Stav."""

    def __init__(self, parent=None) -> None:
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["Položka", "Hodnota", "Stav"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setAlternatingRowColors(True)
        self.setMinimumHeight(180)

    def set_rows(self, rows: list[tuple[str, str, str]]) -> None:
        self.setRowCount(len(rows))
        for row_index, (item_name, value, status) in enumerate(rows):
            self.setItem(row_index, 0, QTableWidgetItem(item_name))
            self.setItem(row_index, 1, QTableWidgetItem(value))
            status_item = QTableWidgetItem(status)
            if status == "Problém":
                status_item.setForeground(Qt.GlobalColor.darkRed)
            self.setItem(row_index, 2, status_item)
