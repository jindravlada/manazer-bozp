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
    CONTACT_TABLE_HEADERS,
    CTC_COL_ACTIVE,
    CTC_COL_EMAIL,
    CTC_COL_ID,
    CTC_COL_NAME,
    CTC_COL_PHONE,
    CTC_COL_ROLE,
    CTC_COL_TYPE,
    CTC_COLUMN_COUNT,
)
from moduly.koordinace_bozp.sluzby.coordination_contact_service import (
    coordination_contact_service,
)


class CoordinationContactTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(CTC_COLUMN_COUNT)
        self.setHorizontalHeaderLabels(CONTACT_TABLE_HEADERS)
        self.setColumnHidden(CTC_COL_ID, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        enable_typed_sorting(self)

    def load_contacts(self, contacts) -> None:
        with sorting_paused(self):
            self.setRowCount(len(contacts))
            for row, item in enumerate(contacts):
                record_id = int(item.id)
                type_label = coordination_contact_service.contact_type_label(
                    item.contact_type
                )
                self.setItem(
                    row,
                    CTC_COL_ID,
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    CTC_COL_TYPE,
                    create_typed_item(
                        type_label,
                        typed_text(type_label),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    CTC_COL_NAME,
                    create_typed_item(
                        item.custom_name or "",
                        typed_text(item.custom_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    CTC_COL_ROLE,
                    create_typed_item(
                        item.role or "",
                        typed_text(item.role),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    CTC_COL_PHONE,
                    create_typed_item(
                        item.phone or "",
                        typed_text(item.phone),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    CTC_COL_EMAIL,
                    create_typed_item(
                        item.email or "",
                        typed_text(item.email),
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
                self.setItem(row, CTC_COL_ACTIVE, active_item)

    def selected_contact_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), CTC_COL_ID)
        if item is None:
            return None
        return int(item.text())

    def clear_selection(self) -> None:
        self.clearSelection()
