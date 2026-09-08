from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.pravni_pozadavky.constants import CHANGE_SECTION_TYPE_LABELS

ROLE_SECTION_ID = Qt.ItemDataRole.UserRole


class LegalChangeSectionsTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self._sections = []

        self.setColumnCount(2)
        self.setHorizontalHeaderLabels([
            "Typ změny",
            "Ustanovení",
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
        self.setColumnWidth(0, 120)

    def load_sections(self, sections) -> None:
        self._sections = list(sections)
        self.setRowCount(len(self._sections))

        for row, section in enumerate(self._sections):
            change_type = CHANGE_SECTION_TYPE_LABELS.get(
                section.change_type,
                section.change_type,
            )
            self._set_item(row, 0, change_type, section.id)
            self._set_item(row, 1, section.section_label, section.id)

    def selected_section(self):
        selected = self.selectionModel().selectedRows() if self.selectionModel() else []
        if not selected:
            return None
        item = self.item(selected[0].row(), 0)
        if item is None:
            return None
        section_id = item.data(ROLE_SECTION_ID)
        for section in self._sections:
            if section.id == section_id:
                return section
        return None

    def _set_item(self, row: int, column: int, text: str, section_id: int) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setData(ROLE_SECTION_ID, section_id)
        self.setItem(row, column, item)
