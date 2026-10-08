"""Přehled platnosti evidovaných zkoušek."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

from core.theme.status_colors import (
    STATUS_DONE_BG,
    STATUS_DONE_TEXT,
    STATUS_IN_PROGRESS_BG,
    STATUS_MISSING_BG,
    STATUS_MISSING_TEXT,
    STATUS_NEUTRAL_BG,
    STATUS_ORANGE_TEXT,
)
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_int,
    typed_text,
)
from moduly.testy.constants import (
    EXAM_VALIDITY_STATE_EXPIRED,
    EXAM_VALIDITY_STATE_EXPIRING,
    EXAM_VALIDITY_STATE_LABELS,
    EXAM_VALIDITY_STATE_NO_SUCCESS,
    EXAM_VALIDITY_STATE_UNLIMITED,
    EXAM_VALIDITY_STATE_VALID,
    VALIDITY_COL_EMPLOYEE,
    VALIDITY_COL_IN_PROGRESS,
    VALIDITY_COL_LAST_SUCCESS,
    VALIDITY_COL_PERSONAL_NUMBER,
    VALIDITY_COL_PREPARED,
    VALIDITY_COL_STATE,
    VALIDITY_COL_TEST,
    VALIDITY_COL_VALID_UNTIL,
    VALIDITY_COL_WORKPLACE,
    VALIDITY_COLUMN_HEADERS,
)
from moduly.testy.sluzby.exam_validity_service import (
    ExamValidityRow,
    exam_validity_search_text,
)
from moduly.testy.sluzby.test_exam_service import format_exam_date

ROLE_SEARCH = Qt.ItemDataRole.UserRole + 1

_STATE_BACKGROUNDS = {
    EXAM_VALIDITY_STATE_VALID: STATUS_DONE_BG,
    EXAM_VALIDITY_STATE_EXPIRING: STATUS_IN_PROGRESS_BG,
    EXAM_VALIDITY_STATE_EXPIRED: STATUS_MISSING_BG,
    EXAM_VALIDITY_STATE_UNLIMITED: STATUS_NEUTRAL_BG,
    EXAM_VALIDITY_STATE_NO_SUCCESS: STATUS_NEUTRAL_BG,
}
_STATE_FOREGROUNDS = {
    EXAM_VALIDITY_STATE_VALID: STATUS_DONE_TEXT,
    EXAM_VALIDITY_STATE_EXPIRING: STATUS_ORANGE_TEXT,
    EXAM_VALIDITY_STATE_EXPIRED: STATUS_MISSING_TEXT,
}


class ExamValidityTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(VALIDITY_COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(VALIDITY_COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.verticalHeader().setDefaultSectionSize(self.fontMetrics().height() + 8)
        self._has_sort = False
        enable_typed_sorting(self)

    def load_rows(self, rows: list[ExamValidityRow]) -> None:
        header = self.horizontalHeader()
        if not self._has_sort:
            header.setSortIndicator(
                VALIDITY_COL_EMPLOYEE,
                Qt.SortOrder.AscendingOrder,
            )
            self._has_sort = True
        with sorting_paused(self):
            self.setRowCount(len(rows))
            for index, row in enumerate(rows):
                state_label = EXAM_VALIDITY_STATE_LABELS.get(row.state, row.state)
                last_success = format_exam_date(row.last_success_on)
                valid_until = format_exam_date(row.valid_until)
                stable_id = int(row.employee_id) * 1_000_003 + int(row.test_definition_id)
                values = {
                    VALIDITY_COL_PERSONAL_NUMBER: (
                        row.personal_number,
                        typed_text(row.personal_number),
                    ),
                    VALIDITY_COL_EMPLOYEE: (row.employee_name, typed_text(row.employee_name)),
                    VALIDITY_COL_WORKPLACE: (row.workplace_name, typed_text(row.workplace_name)),
                    VALIDITY_COL_TEST: (row.test_name, typed_text(row.test_name)),
                    VALIDITY_COL_LAST_SUCCESS: (last_success, typed_date(row.last_success_on)),
                    VALIDITY_COL_VALID_UNTIL: (valid_until, typed_date(row.valid_until)),
                    VALIDITY_COL_STATE: (state_label, typed_text(state_label)),
                    VALIDITY_COL_PREPARED: (str(row.prepared_count), typed_int(row.prepared_count)),
                    VALIDITY_COL_IN_PROGRESS: (
                        str(row.in_progress_count),
                        typed_int(row.in_progress_count),
                    ),
                }
                search = exam_validity_search_text(row)
                for column, (text, sort_value) in values.items():
                    item = create_typed_item(text, sort_value, stable_id=stable_id)
                    if column == VALIDITY_COL_EMPLOYEE:
                        item.setData(ROLE_SEARCH, search)
                    if column == VALIDITY_COL_STATE:
                        _paint_state(item, row.state)
                    self.setItem(index, column, item)


def _paint_state(item, state: str) -> None:
    background = _STATE_BACKGROUNDS.get(state)
    if background:
        item.setBackground(QBrush(QColor(background)))
    foreground = _STATE_FOREGROUNDS.get(state)
    if foreground:
        item.setForeground(QBrush(QColor(foreground)))
