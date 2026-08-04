"""Tabulka společného přehledu Agendy."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_datetime,
    typed_empty,
    typed_text,
)
from moduly.agenda.constants import (
    COL_DUE,
    COL_PERSON,
    COL_SOURCE,
    COL_STATUS,
    COL_TITLE,
    COL_TYPE,
    COLUMN_HEADERS,
)
from moduly.agenda.sluzby.agenda_service import AgendaItem

_ROLE_ITEM = Qt.ItemDataRole.UserRole
_TYPE_STABLE_PREFIX = {
    "task": 1,
    "meeting": 2,
}


class AgendaTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(len(COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        enable_typed_sorting(self)

    def clear_selection(self) -> None:
        self.clearSelection()
        self.setCurrentCell(-1, -1)

    def selected_item(self) -> AgendaItem | None:
        rows = self.selectionModel().selectedRows()
        if not rows:
            return None
        cell = self.item(rows[0].row(), COL_TYPE)
        if cell is None:
            return None
        payload = cell.data(_ROLE_ITEM)
        return payload if isinstance(payload, AgendaItem) else None

    def load_items(self, items: list[AgendaItem]) -> None:
        with sorting_paused(self):
            self.setRowCount(0)
            self.setRowCount(len(items))
            for row, agenda in enumerate(items):
                stable_id = (
                    _TYPE_STABLE_PREFIX.get(agenda.item_type, 9) * 1_000_000_000
                    + int(agenda.source_id)
                )
                type_item = create_typed_item(
                    agenda.type_label,
                    typed_text(agenda.type_label),
                    stable_id=stable_id,
                )
                type_item.setData(_ROLE_ITEM, agenda)
                self.setItem(row, COL_TYPE, type_item)

                due_text = self._format_due(agenda)
                due_dt = agenda.due_sort_datetime
                due_sort = typed_datetime(due_dt) if due_dt is not None else typed_empty()
                self.setItem(
                    row,
                    COL_DUE,
                    create_typed_item(due_text, due_sort, stable_id=stable_id),
                )

                self.setItem(
                    row,
                    COL_TITLE,
                    create_typed_item(agenda.title, typed_text(agenda.title), stable_id=stable_id),
                )

                person = agenda.person or "—"
                person_sort = typed_text(person) if agenda.person else typed_empty()
                self.setItem(
                    row,
                    COL_PERSON,
                    create_typed_item(person, person_sort, stable_id=stable_id),
                )

                status = agenda.status or "—"
                self.setItem(
                    row,
                    COL_STATUS,
                    create_typed_item(status, typed_text(status), stable_id=stable_id),
                )

                source = agenda.source or "—"
                source_sort = typed_text(source) if agenda.source and agenda.source != "—" else typed_empty()
                self.setItem(
                    row,
                    COL_SOURCE,
                    create_typed_item(source, source_sort, stable_id=stable_id),
                )

        if items:
            # Výchozí chronologické řazení (stejná osa jako dashboard).
            self.sortItems(COL_DUE, Qt.SortOrder.AscendingOrder)

    @staticmethod
    def _format_due(agenda: AgendaItem) -> str:
        if agenda.event_at is not None:
            starts = agenda.event_at
            return (
                f"{starts.day}. {starts.month}. {starts.year} "
                f"{starts.hour}:{starts.minute:02d}"
            )
        if agenda.due_date is not None:
            due = agenda.due_date
            return f"{due.day}. {due.month}. {due.year}"
        return "—"
