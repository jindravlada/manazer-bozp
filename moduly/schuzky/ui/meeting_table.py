"""Tabulka přehledu schůzek."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_datetime,
    typed_empty,
    typed_status,
    typed_text,
)
from moduly.schuzky.constants import (
    COL_ID,
    COL_LOCATION,
    COL_ORGANIZER,
    COL_STARTS_AT,
    COL_STATUS,
    COL_TITLE,
    COLUMN_HEADERS,
    MEETING_STATUSES,
)


class MeetingTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(len(COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.setColumnHidden(COL_ID, True)
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

    def load_meetings(self, meetings) -> None:
        with sorting_paused(self):
            self.setRowCount(0)
            self.setRowCount(len(meetings))
            for row, meeting in enumerate(meetings):
                stable_id = int(meeting.id)
                self.setItem(
                    row,
                    COL_ID,
                    create_typed_item(str(meeting.id), typed_text(str(meeting.id)), stable_id=stable_id),
                )
                starts = meeting.starts_at
                starts_text = self._format_dt(starts)
                starts_sort = typed_datetime(starts) if starts is not None else typed_empty()
                self.setItem(
                    row,
                    COL_STARTS_AT,
                    create_typed_item(starts_text, starts_sort, stable_id=stable_id),
                )
                title = meeting.title or "—"
                self.setItem(
                    row,
                    COL_TITLE,
                    create_typed_item(title, typed_text(title), stable_id=stable_id),
                )
                location = meeting.location or "—"
                self.setItem(
                    row,
                    COL_LOCATION,
                    create_typed_item(location, typed_text(location), stable_id=stable_id),
                )
                organizer = meeting.organizer_name or "—"
                self.setItem(
                    row,
                    COL_ORGANIZER,
                    create_typed_item(organizer, typed_text(organizer), stable_id=stable_id),
                )
                status = meeting.status or ""
                try:
                    status_sort = typed_status(MEETING_STATUSES.index(status), label=status)
                except ValueError:
                    status_sort = typed_status(len(MEETING_STATUSES), label=status)
                self.setItem(
                    row,
                    COL_STATUS,
                    create_typed_item(status or "—", status_sort, stable_id=stable_id),
                )

    @staticmethod
    def _format_dt(value: datetime | None) -> str:
        if value is None:
            return "—"
        return value.strftime("%d.%m.%Y %H:%M")
