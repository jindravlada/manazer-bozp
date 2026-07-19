from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_date,
    typed_int,
    typed_text,
)
from moduly.koordinace_bozp.constants import (
    ACT_COL_ACTIVE,
    ACT_COL_FROM,
    ACT_COL_ID,
    ACT_COL_NAME,
    ACT_COL_PLACE,
    ACT_COL_TO,
    ACT_COLUMN_COUNT,
    ACTIVITY_TABLE_HEADERS,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_activity_service import (
    coordination_employer_activity_service,
)


class CoordinationEmployerActivityTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(ACT_COLUMN_COUNT)
        self.setHorizontalHeaderLabels(ACTIVITY_TABLE_HEADERS)
        self.setColumnHidden(ACT_COL_ID, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        enable_typed_sorting(self)

    def load_activities(self, activities) -> None:
        with sorting_paused(self):
            self.setRowCount(len(activities))
            for row, item in enumerate(activities):
                record_id = int(item.id)
                place_label = coordination_employer_activity_service.workplace_label(
                    item.coordination_workplace_id
                )
                from_text = (
                    item.planned_from.strftime("%d.%m.%Y") if item.planned_from else ""
                )
                to_text = item.planned_to.strftime("%d.%m.%Y") if item.planned_to else ""
                self.setItem(
                    row,
                    ACT_COL_ID,
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    ACT_COL_NAME,
                    create_typed_item(
                        item.activity_name or "",
                        typed_text(item.activity_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    ACT_COL_PLACE,
                    create_typed_item(
                        place_label,
                        typed_text(place_label),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    ACT_COL_FROM,
                    create_typed_item(
                        from_text,
                        typed_date(item.planned_from),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    ACT_COL_TO,
                    create_typed_item(
                        to_text,
                        typed_date(item.planned_to),
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
                self.setItem(row, ACT_COL_ACTIVE, active_item)

    def selected_activity_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), ACT_COL_ID)
        if item is None:
            return None
        return int(item.text())

    def clear_selection(self) -> None:
        self.clearSelection()
