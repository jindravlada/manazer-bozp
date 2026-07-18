from PySide6.QtWidgets import QHeaderView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_int,
    typed_text,
)

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

        enable_typed_sorting(self)

    def load_children(self, children) -> None:
        with sorting_paused(self):
            self.setRowCount(len(children))
            for row, requirement in enumerate(children):
                record_id = int(requirement.id)
                self.setItem(
                    row,
                    COL_ID,
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                )
                self.setItem(
                    row,
                    COL_CODE,
                    create_typed_item(
                        requirement.process_code,
                        typed_text(requirement.process_code),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    COL_TITLE,
                    create_typed_item(
                        requirement.title,
                        typed_text(requirement.title),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    COL_ACTIVE,
                    create_typed_item(
                        "Ano" if requirement.active else "Ne",
                        typed_bool(requirement.active),
                        stable_id=record_id,
                    ),
                )

    def selected_requirement_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), COL_ID)
        if item is None or not item.text().strip():
            return None
        return int(item.text())
