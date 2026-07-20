from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget

from core.widgets.table_utils import apply_cell_tooltip
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_int,
    typed_text,
)
from moduly.koordinace_bozp.constants import (
    PART_COL_ACTIVE,
    PART_COL_EMAIL,
    PART_COL_EMPLOYER,
    PART_COL_FULL_NAME,
    PART_COL_ID,
    PART_COL_PHONE,
    PART_COL_ROLE,
    PART_COLUMN_COUNT,
    PARTICIPANT_TABLE_HEADERS,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
    employer_tooltip_name,
)
from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
    coordination_participant_service,
)


class CoordinationParticipantTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(PART_COLUMN_COUNT)
        self.setHorizontalHeaderLabels(PARTICIPANT_TABLE_HEADERS)
        self.setColumnHidden(PART_COL_ID, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        enable_typed_sorting(self)

    def load_participants(self, participants) -> None:
        with sorting_paused(self):
            self.setRowCount(len(participants))
            for row, item in enumerate(participants):
                record_id = int(item.id)
                employer_label = coordination_participant_service.employer_short_label(
                    item.coordination_employer_id
                )
                employer = coordination_employer_service.get_by_id(
                    item.coordination_employer_id
                )
                employer_tip = employer_tooltip_name(employer) or employer_label
                self.setItem(
                    row,
                    PART_COL_ID,
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                )
                employer_item = create_typed_item(
                    employer_label,
                    typed_text(employer_label),
                    stable_id=record_id,
                )
                apply_cell_tooltip(employer_item, employer_tip)
                self.setItem(row, PART_COL_EMPLOYER, employer_item)
                name_text = item.full_name or ""
                name_item = create_typed_item(
                    name_text,
                    typed_text(item.full_name),
                    stable_id=record_id,
                )
                apply_cell_tooltip(name_item, name_text)
                self.setItem(row, PART_COL_FULL_NAME, name_item)
                role_text = item.role or ""
                role_item = create_typed_item(
                    role_text,
                    typed_text(item.role),
                    stable_id=record_id,
                )
                apply_cell_tooltip(role_item, role_text)
                self.setItem(row, PART_COL_ROLE, role_item)
                self.setItem(
                    row,
                    PART_COL_PHONE,
                    create_typed_item(
                        item.phone or "",
                        typed_text(item.phone),
                        stable_id=record_id,
                    ),
                )
                email_text = item.email or ""
                email_item = create_typed_item(
                    email_text,
                    typed_text(item.email),
                    stable_id=record_id,
                )
                apply_cell_tooltip(email_item, email_text)
                self.setItem(row, PART_COL_EMAIL, email_item)
                active_item = create_typed_item(
                    "Ano" if item.active else "Ne",
                    typed_bool(bool(item.active)),
                    stable_id=record_id,
                )
                if not item.active:
                    active_item.setData(Qt.ItemDataRole.UserRole + 1, False)
                self.setItem(row, PART_COL_ACTIVE, active_item)

    def selected_participant_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), PART_COL_ID)
        if item is None:
            return None
        return int(item.text())

    def clear_selection(self) -> None:
        self.clearSelection()
