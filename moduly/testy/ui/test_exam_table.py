"""Seznam připravených zkoušek."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QTableWidget

from core.theme.status_colors import STATUS_DONE_BG, STATUS_DONE_TEXT, STATUS_NEUTRAL_BG

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_text,
)
from moduly.testy.constants import (
    EXAM_COL_DATE,
    EXAM_COL_EMPLOYEE,
    EXAM_COL_EXAM_RESULT,
    EXAM_COL_ID,
    EXAM_COL_PROTOCOL,
    EXAM_COL_STATUS,
    EXAM_COL_TEST,
    EXAM_COL_VALID_UNTIL,
    EXAM_COL_WRITTEN_RESULT,
    EXAM_COLUMN_HEADERS,
    EXAM_PROTOCOL_ATTACHED,
    EXAM_PROTOCOL_MISSING,
    EXAM_PROTOCOL_NOT_APPLICABLE,
    EXAM_STATUS_COMPLETED,
    EXAM_STATUS_LABELS,
    written_result_label,
)
from moduly.testy.modely.test_exam import TestExam
from moduly.testy.sluzby.test_exam_service import format_exam_date

_ROLE_ID = Qt.ItemDataRole.UserRole
_ROLE_SEARCH = Qt.ItemDataRole.UserRole + 1


class TestExamTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(EXAM_COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(EXAM_COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setColumnHidden(EXAM_COL_ID, True)
        enable_typed_sorting(self)

    def selected_exam_id(self) -> int | None:
        rows = self.selectionModel().selectedRows() if self.selectionModel() else []
        if len(rows) != 1:
            return None
        item = self.item(rows[0].row(), EXAM_COL_ID)
        if item is None:
            return None
        try:
            return int(item.data(_ROLE_ID))
        except (TypeError, ValueError):
            return None

    def load_exams(self, exams: list[TestExam]) -> None:
        with sorting_paused(self):
            self.setRowCount(len(exams))
            for row, exam in enumerate(exams):
                status = EXAM_STATUS_LABELS.get(exam.status, exam.status)
                written_result = written_result_label(exam.written_result)
                exam_result = written_result_label(exam.exam_result)
                protocol = _protocol_label(exam)
                values = {
                    EXAM_COL_ID: (str(exam.id), typed_text(str(exam.id))),
                    EXAM_COL_DATE: (format_exam_date(exam.exam_date), typed_date(exam.exam_date)),
                    EXAM_COL_EMPLOYEE: (
                        exam.employee_display_name,
                        typed_text(exam.employee_display_name),
                    ),
                    EXAM_COL_TEST: (exam.test_name, typed_text(exam.test_name)),
                    EXAM_COL_VALID_UNTIL: (
                        format_exam_date(exam.valid_until),
                        typed_date(exam.valid_until),
                    ),
                    EXAM_COL_STATUS: (status, typed_text(status)),
                    EXAM_COL_WRITTEN_RESULT: (written_result, typed_text(written_result)),
                    EXAM_COL_EXAM_RESULT: (exam_result, typed_text(exam_result)),
                    EXAM_COL_PROTOCOL: (protocol, typed_text(protocol)),
                }
                search = " ".join(
                    [
                        exam.employee_personal_number,
                        exam.employee_first_name,
                        exam.employee_last_name,
                        exam.employee_display_name,
                        exam.test_name,
                    ]
                )
                for column, (text, sort_value) in values.items():
                    item = create_typed_item(text, sort_value, stable_id=exam.id)
                    item.setData(_ROLE_ID, exam.id)
                    if column == EXAM_COL_EMPLOYEE:
                        item.setData(_ROLE_SEARCH, search)
                    if column == EXAM_COL_PROTOCOL:
                        _paint_protocol(item, text)
                    self.setItem(row, column, item)


def _protocol_label(exam: TestExam) -> str:
    if exam.status != EXAM_STATUS_COMPLETED:
        return EXAM_PROTOCOL_NOT_APPLICABLE
    if exam.signed_protocol_attachment_id:
        return EXAM_PROTOCOL_ATTACHED
    return EXAM_PROTOCOL_MISSING


def _paint_protocol(item, text: str) -> None:
    if text == EXAM_PROTOCOL_ATTACHED:
        item.setBackground(QBrush(QColor(STATUS_DONE_BG)))
        item.setForeground(QBrush(QColor(STATUS_DONE_TEXT)))
        return
    item.setBackground(QBrush(QColor(STATUS_NEUTRAL_BG)))
