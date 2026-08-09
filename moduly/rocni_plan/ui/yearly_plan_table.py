"""Tabulka položek Ročního plánu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_text,
)
from moduly.rocni_plan.constants import (
    COL_ID,
    COL_LINK,
    COL_NOTE,
    COL_SOURCE,
    COL_STATUS,
    COL_TITLE,
    COLUMN_HEADERS,
    ROW_KIND_MANUAL,
    ROW_KIND_PERIODIC,
    status_label,
)
from moduly.rocni_plan.modely.yearly_plan_row import YearlyPlanRow

_ROLE_PLAN_ITEM_ID = Qt.ItemDataRole.UserRole
_ROLE_KIND = Qt.ItemDataRole.UserRole + 1
_ROLE_ACTIVITY_ID = Qt.ItemDataRole.UserRole + 2
_ROLE_DISPLAY_STATUS = Qt.ItemDataRole.UserRole + 3
_ROLE_SLOT_YEAR = Qt.ItemDataRole.UserRole + 4
_ROLE_SLOT_MONTH = Qt.ItemDataRole.UserRole + 5
_ROLE_IS_RECURRING = Qt.ItemDataRole.UserRole + 6


class YearlyPlanTable(QTableWidget):
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
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        enable_typed_sorting(self)

    def clear_selection(self) -> None:
        self.clearSelection()
        self.setCurrentCell(-1, -1)

    def _selected_id_item(self):
        rows = self.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        return self.item(rows[0].row(), COL_ID)

    def selected_item_id(self) -> int | None:
        """ID ruční položky / definice, nebo None u Periodické činnosti."""
        item = self._selected_id_item()
        if item is None:
            return None
        if item.data(_ROLE_KIND) != ROW_KIND_MANUAL:
            return None
        raw = item.data(_ROLE_PLAN_ITEM_ID)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def selected_activity_id(self) -> int | None:
        item = self._selected_id_item()
        if item is None:
            return None
        if item.data(_ROLE_KIND) != ROW_KIND_PERIODIC:
            return None
        raw = item.data(_ROLE_ACTIVITY_ID)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def selected_kind(self) -> str | None:
        item = self._selected_id_item()
        if item is None:
            return None
        kind = item.data(_ROLE_KIND)
        return str(kind) if kind else None

    def selected_is_periodic(self) -> bool:
        return self.selected_kind() == ROW_KIND_PERIODIC

    def selected_is_manual(self) -> bool:
        return self.selected_kind() == ROW_KIND_MANUAL

    def selected_is_recurring(self) -> bool:
        item = self._selected_id_item()
        if item is None:
            return False
        return bool(item.data(_ROLE_IS_RECURRING))

    def selected_slot_year_month(self) -> tuple[int, int] | None:
        item = self._selected_id_item()
        if item is None:
            return None
        year = item.data(_ROLE_SLOT_YEAR)
        month = item.data(_ROLE_SLOT_MONTH)
        try:
            return int(year), int(month)
        except (TypeError, ValueError):
            return None

    def load_rows(self, rows: list[YearlyPlanRow]) -> None:
        with sorting_paused(self):
            self.setRowCount(0)
            self.setRowCount(len(rows))
            for row_index, plan_row in enumerate(rows):
                if plan_row.plan_item_id is not None:
                    stable_id = (
                        int(plan_row.plan_item_id) * 100_000
                        + (plan_row.slot_year or 0) * 12
                        + (plan_row.slot_month or 0)
                    )
                    id_text = str(plan_row.plan_item_id)
                else:
                    stable_id = 1_000_000_000 + (plan_row.activity_id or 0)
                    id_text = f"P{plan_row.activity_id or 0}"
                id_item = create_typed_item(
                    id_text,
                    typed_text(id_text),
                    stable_id=stable_id,
                )
                id_item.setData(_ROLE_PLAN_ITEM_ID, plan_row.plan_item_id)
                id_item.setData(_ROLE_KIND, plan_row.kind)
                id_item.setData(_ROLE_ACTIVITY_ID, plan_row.activity_id)
                id_item.setData(_ROLE_SLOT_YEAR, plan_row.slot_year)
                id_item.setData(_ROLE_SLOT_MONTH, plan_row.slot_month)
                id_item.setData(_ROLE_IS_RECURRING, bool(plan_row.is_recurring))
                self.setItem(row_index, COL_ID, id_item)

                source = plan_row.source_label or "—"
                self.setItem(
                    row_index,
                    COL_SOURCE,
                    create_typed_item(source, typed_text(source), stable_id=stable_id),
                )

                title = (plan_row.title or "").strip() or "—"
                self.setItem(
                    row_index,
                    COL_TITLE,
                    create_typed_item(title, typed_text(title), stable_id=stable_id),
                )

                status_text = status_label(plan_row.display_status)
                status_item = create_typed_item(
                    status_text,
                    typed_text(status_text),
                    stable_id=stable_id,
                )
                status_item.setData(_ROLE_DISPLAY_STATUS, plan_row.display_status)
                self.setItem(row_index, COL_STATUS, status_item)

                link_text = plan_row.link_text or "—"
                self.setItem(
                    row_index,
                    COL_LINK,
                    create_typed_item(
                        link_text,
                        typed_text(link_text),
                        stable_id=stable_id,
                    ),
                )

                note = (plan_row.note or "").strip() or "—"
                self.setItem(
                    row_index,
                    COL_NOTE,
                    create_typed_item(note, typed_text(note), stable_id=stable_id),
                )
