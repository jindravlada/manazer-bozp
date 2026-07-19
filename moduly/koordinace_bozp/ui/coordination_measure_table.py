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
    MEASURE_TABLE_HEADERS,
    MSR_COL_ACTIVE,
    MSR_COL_CATEGORY,
    MSR_COL_ID,
    MSR_COL_TITLE,
    MSR_COLUMN_COUNT,
)
from moduly.koordinace_bozp.sluzby.coordination_measure_service import (
    coordination_measure_service,
)


class CoordinationMeasureTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(MSR_COLUMN_COUNT)
        self.setHorizontalHeaderLabels(MEASURE_TABLE_HEADERS)
        self.setColumnHidden(MSR_COL_ID, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        enable_typed_sorting(self)

    def load_measures(self, measures) -> None:
        with sorting_paused(self):
            self.setRowCount(len(measures))
            for row, item in enumerate(measures):
                record_id = int(item.id)
                category_label = coordination_measure_service.category_label(item.category)
                self.setItem(
                    row,
                    MSR_COL_ID,
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    MSR_COL_CATEGORY,
                    create_typed_item(
                        category_label,
                        typed_text(category_label),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    MSR_COL_TITLE,
                    create_typed_item(
                        item.title or "",
                        typed_text(item.title),
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
                self.setItem(row, MSR_COL_ACTIVE, active_item)

    def selected_measure_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), MSR_COL_ID)
        if item is None:
            return None
        return int(item.text())

    def clear_selection(self) -> None:
        self.clearSelection()
