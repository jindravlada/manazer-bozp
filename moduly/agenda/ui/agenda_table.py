"""Tabulka společného přehledu Agendy."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

from core.dashboard.attention_item import priority_then_due_sort_int
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_datetime,
    typed_empty,
    typed_int,
    typed_text,
)
from moduly.agenda.constants import (
    COL_DEFAULT_SORT,
    COL_DUE,
    COL_PERSON,
    COL_SOURCE,
    COL_STATUS,
    COL_TITLE,
    COL_TYPE,
    COLUMN_HEADERS,
    DEFAULT_PRIORITY_COLOR,
    PRIORITY_COLORS,
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
        self.setColumnCount(len(COLUMN_HEADERS) + 1)
        self.setHorizontalHeaderLabels([*COLUMN_HEADERS, ""])
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        self.setColumnHidden(COL_DEFAULT_SORT, True)
        enable_typed_sorting(self)
        self.horizontalHeader().setSortIndicator(
            COL_DEFAULT_SORT,
            Qt.SortOrder.AscendingOrder,
        )

    def clear_selection(self) -> None:
        self.clearSelection()
        self.setCurrentCell(-1, -1)

    def selected_item(self) -> AgendaItem | None:
        rows = self.selectionModel().selectedRows()
        if not rows:
            return None
        cell = self.item(rows[0].row(), COL_TITLE)
        if cell is None:
            return None
        payload = cell.data(_ROLE_ITEM)
        return payload if isinstance(payload, AgendaItem) else None

    def load_items(self, items: list[AgendaItem]) -> None:
        with sorting_paused(self):
            self.setRowCount(0)
            self.setRowCount(len(items))
            for row, agenda in enumerate(items):
                identity_extra = 0
                identity_key = (agenda.identity_key or "").strip()
                if identity_key:
                    identity_extra = abs(hash(identity_key)) % 100_000
                stable_id = (
                    _TYPE_STABLE_PREFIX.get(agenda.item_type, 9) * 1_000_000_000
                    + int(agenda.source_id) * 100_000
                    + identity_extra
                )
                brush = QBrush(self._row_color(agenda.priority))

                title_item = create_typed_item(
                    agenda.title,
                    typed_text(agenda.title),
                    stable_id=stable_id,
                )
                title_item.setData(_ROLE_ITEM, agenda)
                title_item.setBackground(brush)
                self.setItem(row, COL_TITLE, title_item)

                due_text = self._format_due(agenda)
                due_dt = agenda.due_sort_datetime
                due_sort = typed_datetime(due_dt) if due_dt is not None else typed_empty()
                due_item = create_typed_item(due_text, due_sort, stable_id=stable_id)
                due_item.setBackground(brush)
                self.setItem(row, COL_DUE, due_item)

                person = agenda.person or "—"
                person_sort = typed_text(person) if agenda.person else typed_empty()
                person_item = create_typed_item(person, person_sort, stable_id=stable_id)
                person_item.setBackground(brush)
                self.setItem(row, COL_PERSON, person_item)

                status = agenda.status or "—"
                status_item = create_typed_item(status, typed_text(status), stable_id=stable_id)
                status_item.setBackground(brush)
                self.setItem(row, COL_STATUS, status_item)

                source = agenda.source or "—"
                source_sort = (
                    typed_text(source) if agenda.source and agenda.source != "—" else typed_empty()
                )
                source_item = create_typed_item(source, source_sort, stable_id=stable_id)
                source_item.setBackground(brush)
                self.setItem(row, COL_SOURCE, source_item)

                type_item = create_typed_item(
                    agenda.type_label,
                    typed_text(agenda.type_label),
                    stable_id=stable_id,
                )
                type_item.setBackground(brush)
                self.setItem(row, COL_TYPE, type_item)

                default_sort = typed_int(
                    priority_then_due_sort_int(agenda.priority, agenda.due_sort_datetime)
                )
                default_item = create_typed_item("", default_sort, stable_id=stable_id)
                default_item.setBackground(brush)
                self.setItem(row, COL_DEFAULT_SORT, default_item)

        if items:
            self.sortItems(COL_DEFAULT_SORT, Qt.SortOrder.AscendingOrder)

    @staticmethod
    def _row_color(priority: str) -> QColor:
        return QColor(PRIORITY_COLORS.get(priority, DEFAULT_PRIORITY_COLOR))

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
