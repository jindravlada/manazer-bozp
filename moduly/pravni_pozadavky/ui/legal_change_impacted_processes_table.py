from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.pravni_pozadavky.sluzby.legal_change_impacted_process_service import (
    ImpactedControlProcess,
)


class LegalChangeImpactedProcessesTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(2)
        self.setHorizontalHeaderLabels([
            "Kód procesu",
            "Název procesu",
        ])

        self.setWordWrap(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.setColumnWidth(0, 120)

    def load_processes(self, processes: list[ImpactedControlProcess]) -> None:
        self.setRowCount(len(processes))

        for row, process in enumerate(processes):
            self._set_item(row, 0, process.process_code)
            self._set_item(row, 1, process.process_name)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)
