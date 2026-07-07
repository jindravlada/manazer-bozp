from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.pravni_pozadavky.constants import SECTION_TYPE_LABELS


class LegalSectionTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(9)
        self.setHorizontalHeaderLabels([
            "ID",
            "Typ",
            "Číslo",
            "§",
            "Písmeno",
            "Název",
            "Pořadí",
            "Aktivní",
            "Požadavek",
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
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        for column in (1, 2, 3, 4, 6, 7, 8):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(1, 100)
        self.setColumnWidth(2, 70)
        self.setColumnWidth(3, 50)
        self.setColumnWidth(4, 70)
        self.setColumnWidth(6, 70)
        self.setColumnWidth(7, 80)
        self.setColumnWidth(8, 90)

    def load_sections(
        self,
        sections,
        *,
        sections_with_requirements: set[int] | None = None,
    ) -> None:
        requirement_section_ids = sections_with_requirements or set()
        self.setRowCount(len(sections))

        for row, section in enumerate(sections):
            section_type = SECTION_TYPE_LABELS.get(
                section.section_type,
                section.section_type,
            )
            self._set_item(row, 0, str(section.id))
            self._set_item(row, 1, section_type)
            self._set_item(row, 2, section.section_number)
            self._set_item(row, 3, section.paragraph)
            self._set_item(row, 4, section.item_letter)
            self._set_item(row, 5, section.title)
            self._set_item(row, 6, str(section.sort_order))
            self._set_item(row, 7, "Ano" if section.active else "Ne")
            self._set_item(
                row,
                8,
                "Ano" if section.id in requirement_section_ids else "Ne",
            )

            if not section.active:
                brush = QBrush(QColor("#f0f0f0"))
                for column in range(self.columnCount()):
                    item = self.item(row, column)
                    if item is not None:
                        item.setBackground(brush)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)

    def selected_section_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        return int(item.text()) if item else None
