"""Tabulka přehledu Periodických činností."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_empty,
    typed_int,
    typed_text,
)
from moduly.periodicke_cinnosti.constants import (
    COL_ACTIVE,
    COL_ID,
    COL_NEXT_DUE,
    COL_NOTIFY,
    COL_PERIOD,
    COL_PLACE,
    COL_RESPONSIBLE,
    COL_TITLE,
    COLUMN_HEADERS,
    format_calendar_interval,
    format_calendar_start,
    format_place,
)
from moduly.periodicke_cinnosti.modely.periodic_activity import PeriodicActivity

_ROLE_ID = Qt.ItemDataRole.UserRole


class PeriodicActivityTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setColumnHidden(COL_ID, True)
        self.setColumnHidden(COL_NOTIFY, True)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        enable_typed_sorting(self)

    def clear_selection(self) -> None:
        self.clearSelection()
        self.setCurrentCell(-1, -1)

    def selected_activity_id(self) -> int | None:
        rows = self.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        item = self.item(rows[0].row(), COL_ID)
        if item is None:
            return None
        raw = item.data(_ROLE_ID)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def load_activities(self, activities: list[PeriodicActivity]) -> None:
        with sorting_paused(self):
            self.setRowCount(0)
            self.setRowCount(len(activities))
            for row, activity in enumerate(activities):
                id_item = create_typed_item(
                    str(activity.id),
                    typed_text(str(activity.id)),
                    stable_id=activity.id,
                )
                id_item.setData(_ROLE_ID, activity.id)
                self.setItem(row, COL_ID, id_item)

                self.setItem(
                    row,
                    COL_TITLE,
                    create_typed_item(activity.title, typed_text(activity.title), stable_id=activity.id),
                )
                place = format_place(activity)
                self.setItem(
                    row,
                    COL_PLACE,
                    create_typed_item(place, typed_text(place), stable_id=activity.id),
                )
                responsible = (activity.responsible_person_name or "").strip() or "—"
                self.setItem(
                    row,
                    COL_RESPONSIBLE,
                    create_typed_item(responsible, typed_text(responsible), stable_id=activity.id),
                )

                start_text = format_calendar_start(
                    activity.calendar_start_year,
                    activity.calendar_start_month,
                )
                if start_text == "—":
                    start_sort = typed_empty()
                else:
                    start_sort = typed_int(
                        int(activity.calendar_start_year) * 12
                        + int(activity.calendar_start_month)
                    )
                self.setItem(
                    row,
                    COL_NEXT_DUE,
                    create_typed_item(start_text, start_sort, stable_id=activity.id),
                )

                interval = activity.calendar_interval_months
                interval_text = format_calendar_interval(interval)
                interval_sort = typed_int(int(interval)) if interval_text != "—" else typed_empty()
                self.setItem(
                    row,
                    COL_PERIOD,
                    create_typed_item(interval_text, interval_sort, stable_id=activity.id),
                )
                self.setItem(
                    row,
                    COL_NOTIFY,
                    create_typed_item("", typed_empty(), stable_id=activity.id),
                )
                active_text = "Ano" if activity.active else "Ne"
                self.setItem(
                    row,
                    COL_ACTIVE,
                    create_typed_item(
                        active_text,
                        typed_bool(activity.active),
                        stable_id=activity.id,
                    ),
                )
