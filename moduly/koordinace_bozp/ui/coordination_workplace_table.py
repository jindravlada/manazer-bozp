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
    WP_COL_ACTIVE,
    WP_COL_ID,
    WP_COL_NOTE,
    WP_COL_OPERATION,
    WP_COL_PART,
    WP_COL_WORKPLACE,
    WP_COLUMN_COUNT,
    WORKPLACE_TABLE_HEADERS,
)
from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
    coordination_workplace_service,
)


class CoordinationWorkplaceTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(WP_COLUMN_COUNT)
        self.setHorizontalHeaderLabels(WORKPLACE_TABLE_HEADERS)
        self.setColumnHidden(WP_COL_ID, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        enable_typed_sorting(self)

    def load_workplaces(self, workplaces) -> None:
        with sorting_paused(self):
            self.setRowCount(len(workplaces))
            for row, item in enumerate(workplaces):
                record_id = int(item.id)
                operation_name, workplace_name, part_name = (
                    coordination_workplace_service.workplace_display_names(item)
                )
                self.setItem(
                    row,
                    WP_COL_ID,
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    WP_COL_OPERATION,
                    create_typed_item(
                        operation_name,
                        typed_text(operation_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    WP_COL_WORKPLACE,
                    create_typed_item(
                        workplace_name,
                        typed_text(workplace_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    WP_COL_PART,
                    create_typed_item(
                        part_name,
                        typed_text(part_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    WP_COL_NOTE,
                    create_typed_item(
                        item.note or "",
                        typed_text(item.note),
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
                self.setItem(row, WP_COL_ACTIVE, active_item)

    def selected_workplace_link_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), WP_COL_ID)
        if item is None:
            return None
        return int(item.text())

    def clear_selection(self) -> None:
        self.clearSelection()
