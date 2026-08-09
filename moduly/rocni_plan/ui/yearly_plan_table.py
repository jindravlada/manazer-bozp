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
    COL_STATUS,
    COL_TITLE,
    COLUMN_HEADERS,
    link_label,
    status_label,
)
from moduly.rocni_plan.modely.yearly_plan_item import YearlyPlanItem

_ROLE_ID = Qt.ItemDataRole.UserRole


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

    def selected_item_id(self) -> int | None:
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

    def load_items(self, items: list[YearlyPlanItem]) -> None:
        with sorting_paused(self):
            self.setRowCount(0)
            self.setRowCount(len(items))
            for row, plan_item in enumerate(items):
                id_item = create_typed_item(
                    str(plan_item.id),
                    typed_text(str(plan_item.id)),
                    stable_id=plan_item.id,
                )
                id_item.setData(_ROLE_ID, plan_item.id)
                self.setItem(row, COL_ID, id_item)

                title = (plan_item.title or "").strip() or "—"
                self.setItem(
                    row,
                    COL_TITLE,
                    create_typed_item(title, typed_text(title), stable_id=plan_item.id),
                )

                status_text = status_label(plan_item.status)
                self.setItem(
                    row,
                    COL_STATUS,
                    create_typed_item(
                        status_text,
                        typed_text(status_text),
                        stable_id=plan_item.id,
                    ),
                )

                link_text = link_label(plan_item)
                self.setItem(
                    row,
                    COL_LINK,
                    create_typed_item(
                        link_text,
                        typed_text(link_text),
                        stable_id=plan_item.id,
                    ),
                )

                note = (plan_item.note or "").strip() or "—"
                self.setItem(
                    row,
                    COL_NOTE,
                    create_typed_item(note, typed_text(note), stable_id=plan_item.id),
                )
