from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_int,
    typed_text,
)
from moduly.koordinace_bozp.constants import (
    EMP_COL_ABBREVIATION,
    EMP_COL_ACTIVE,
    EMP_COL_ICO,
    EMP_COL_ID,
    EMP_COL_IS_MAIN,
    EMP_COL_NAME,
    EMP_COLUMN_COUNT,
    EMPLOYER_TABLE_HEADERS,
)


class CoordinationEmployerTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(EMP_COLUMN_COUNT)
        self.setHorizontalHeaderLabels(EMPLOYER_TABLE_HEADERS)
        self.setColumnHidden(EMP_COL_ID, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        enable_typed_sorting(self)

    def load_employers(self, employers) -> None:
        with sorting_paused(self):
            self.setRowCount(len(employers))
            for row, item in enumerate(employers):
                record_id = int(item.id)
                self.setItem(
                    row,
                    EMP_COL_ID,
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    EMP_COL_ABBREVIATION,
                    create_typed_item(
                        item.abbreviation or "",
                        typed_text(item.abbreviation),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    EMP_COL_NAME,
                    create_typed_item(
                        item.company_name or "",
                        typed_text(item.company_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    EMP_COL_ICO,
                    create_typed_item(
                        item.ico or "",
                        typed_text(item.ico),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    EMP_COL_IS_MAIN,
                    create_typed_item(
                        "Ano" if item.is_main else "Ne",
                        typed_bool(bool(item.is_main)),
                        stable_id=record_id,
                    ),
                )
                active_item = create_typed_item(
                    "Ano" if item.active else "Ne",
                    typed_bool(bool(item.active)),
                    stable_id=record_id,
                )
                if not item.active:
                    active_item.setData(Qt.ItemDataRole.UserRole + 1, False)
                self.setItem(row, EMP_COL_ACTIVE, active_item)

    def selected_employer_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), EMP_COL_ID)
        if item is None:
            return None
        return int(item.text())

    def clear_selection(self) -> None:
        self.clearSelection()
