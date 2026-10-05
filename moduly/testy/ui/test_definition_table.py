"""Tabulka definic Testů."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_int,
    typed_text,
)
from moduly.testy.constants import (
    PART_NO_LABEL,
    PART_YES_LABEL,
    STATUS_ACTIVE_LABEL,
    STATUS_INACTIVE_LABEL,
    TEST_COL_ID,
    TEST_COL_NAME,
    TEST_COL_ORAL,
    TEST_COL_QUESTION_COUNT,
    TEST_COL_STATUS,
    TEST_COL_VALIDITY,
    TEST_COL_WRITTEN,
    TEST_COLUMN_HEADERS,
)
from moduly.testy.modely.test_definition import TestDefinition
from moduly.testy.sluzby.test_definition_service import (
    format_validity,
    test_definition_service,
)

_ROLE_ID = Qt.ItemDataRole.UserRole
_ROLE_DESCRIPTION = Qt.ItemDataRole.UserRole + 1


class TestDefinitionTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(TEST_COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(TEST_COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setColumnHidden(TEST_COL_ID, True)
        enable_typed_sorting(self)

    def selected_test_id(self) -> int | None:
        rows = self.selectionModel().selectedRows() if self.selectionModel() else []
        if len(rows) != 1:
            return None
        item = self.item(rows[0].row(), TEST_COL_ID)
        if item is None:
            return None
        raw = item.data(_ROLE_ID)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def load_tests(self, tests: list[TestDefinition]) -> None:
        with sorting_paused(self):
            self.setRowCount(len(tests))
            for row, test in enumerate(tests):
                status = STATUS_ACTIVE_LABEL if test.active else STATUS_INACTIVE_LABEL
                question_count = test_definition_service.written_question_count(test.id)
                values = {
                    TEST_COL_ID: (str(test.id), typed_text(str(test.id))),
                    TEST_COL_NAME: (test.name, typed_text(test.name)),
                    TEST_COL_WRITTEN: (
                        PART_YES_LABEL if test.uses_written else PART_NO_LABEL,
                        typed_text(PART_YES_LABEL if test.uses_written else PART_NO_LABEL),
                    ),
                    TEST_COL_ORAL: (
                        PART_YES_LABEL if test.uses_oral else PART_NO_LABEL,
                        typed_text(PART_YES_LABEL if test.uses_oral else PART_NO_LABEL),
                    ),
                    TEST_COL_QUESTION_COUNT: (
                        str(question_count),
                        typed_int(question_count),
                    ),
                    TEST_COL_VALIDITY: (
                        format_validity(test.validity_value, test.validity_unit),
                        typed_text(format_validity(test.validity_value, test.validity_unit)),
                    ),
                    TEST_COL_STATUS: (status, typed_text(status)),
                }
                for column, (text, sort_value) in values.items():
                    item = create_typed_item(text, sort_value, stable_id=test.id)
                    item.setData(_ROLE_ID, test.id)
                    if column == TEST_COL_NAME:
                        item.setData(
                            _ROLE_DESCRIPTION,
                            " ".join((test.description or "").split()),
                        )
                    self.setItem(row, column, item)
