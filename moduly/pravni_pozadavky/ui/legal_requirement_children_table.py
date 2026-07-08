from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

COL_ID = 0
COL_CODE = 1
COL_TITLE = 2
COL_ACTIVE = 3
COLUMN_COUNT = 4


class LegalRequirementChildrenTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(COLUMN_COUNT)
        self.setHorizontalHeaderLabels([
            "ID",
            "Kód procesu",
            "Název procesu",
            "Aktivní",
        ])

        self.setColumnHidden(COL_ID, True)
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
        header.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        for column in (COL_CODE, COL_ACTIVE):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.setColumnWidth(COL_CODE, 110)
        self.setColumnWidth(COL_ACTIVE, 80)

    def load_children(self, children) -> None:
        self.setRowCount(len(children))
        for row, requirement in enumerate(children):
            self._set_item(row, COL_ID, str(requirement.id))
            self._set_item(row, COL_CODE, requirement.process_code)
            self._set_item(row, COL_TITLE, requirement.title)
            self._set_item(row, COL_ACTIVE, "Ano" if requirement.active else "Ne")

    def selected_requirement_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), COL_ID)
        if item is None or not item.text().strip():
            return None
        return int(item.text())

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)
