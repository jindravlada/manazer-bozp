from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.pravni_pozadavky.constants import CHANGE_SECTION_TYPE_LABELS


class LegalChangeSectionsTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(3)
        self.setHorizontalHeaderLabels([
            "Typ změny",
            "Ustanovení",
            "Poznámka",
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
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.setColumnWidth(0, 120)

    def load_sections(self, sections) -> None:
        self.setRowCount(len(sections))

        for row, section in enumerate(sections):
            change_type = CHANGE_SECTION_TYPE_LABELS.get(
                section.change_type,
                section.change_type,
            )
            self._set_item(row, 0, change_type)
            self._set_item(row, 1, section.section_label)
            self._set_item(row, 2, section.note or "")

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)
