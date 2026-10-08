"""Záložka evidenčního přehledu platnosti zkoušek. Jen pro čtení."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.czech_sort import czech_sort_key
from core.widgets.filter_bar import FilterBar
from core.widgets.no_wheel_guards import NoWheelComboBox
from core.widgets.table_utils import configure_table_columns
from moduly.testy.constants import (
    EXAM_VALIDITY_FILTER_ALL_STATES,
    EXAM_VALIDITY_FILTER_ALL_TESTS,
    EXAM_VALIDITY_FILTER_ALL_WORKPLACES,
    EXAM_VALIDITY_SEARCH_PLACEHOLDER,
    EXAM_VALIDITY_SHOW_INACTIVE,
    EXAM_VALIDITY_STATE_LABELS,
    EXAM_VALIDITY_STATE_ORDER,
    VALIDITY_COL_EMPLOYEE,
)
from moduly.testy.sluzby.exam_validity_service import (
    ExamValidityRow,
    exam_validity_service,
    filter_exam_validity_rows,
)
from moduly.testy.ui.exam_validity_table import ROLE_SEARCH, ExamValidityTable


class ExamValidityTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.today_override: date | None = None
        self._base_rows: list[ExamValidityRow] = []
        self._reloading_filters = False

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.workplace_filter = NoWheelComboBox()
        self.workplace_filter.setMinimumWidth(180)
        self.test_filter = NoWheelComboBox()
        self.test_filter.setMinimumWidth(180)
        self.state_filter = NoWheelComboBox()
        self.state_filter.setMinimumWidth(180)
        self.show_inactive = QCheckBox(EXAM_VALIDITY_SHOW_INACTIVE)
        toolbar.addWidget(QLabel("Pracoviště:"))
        toolbar.addWidget(self.workplace_filter)
        toolbar.addWidget(QLabel("Test:"))
        toolbar.addWidget(self.test_filter)
        toolbar.addWidget(QLabel("Stav platnosti:"))
        toolbar.addWidget(self.state_filter)
        toolbar.addStretch()
        toolbar.addWidget(self.show_inactive)

        self.table = ExamValidityTable()
        configure_table_columns(self.table, "test_exam_validity")
        self.text_filter = FilterBar(
            self.table,
            placeholder=EXAM_VALIDITY_SEARCH_PLACEHOLDER,
            apply_fn=self._apply_search,
        )

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)

        self._fill_state_filter()
        self.workplace_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.test_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.state_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.show_inactive.toggled.connect(self.refresh)
        self.refresh()

    def current_day(self) -> date:
        if self.today_override is not None:
            return self.today_override
        return date.today()

    def refresh(self) -> None:
        if self._reloading_filters:
            return
        self._base_rows = exam_validity_service.list_rows(
            today=self.current_day(),
            include_inactive_employees=self.show_inactive.isChecked(),
        )
        self._reload_choice_filters(self._base_rows)
        self._apply_current_filters()

    def _on_filter_changed(self) -> None:
        if self._reloading_filters:
            return
        self._apply_current_filters()

    def _apply_current_filters(self) -> None:
        rows = filter_exam_validity_rows(
            self._base_rows,
            workplace_id=self._selected_id(self.workplace_filter),
            test_definition_id=self._selected_id(self.test_filter),
            state=self._selected_state(),
        )
        self.table.load_rows(rows)
        configure_table_columns(self.table, "test_exam_validity")
        self.text_filter.apply_filter()

    def _apply_search(self, text: str) -> tuple[int, int]:
        needle = " ".join(text.casefold().split())
        total = self.table.rowCount()
        visible = 0
        for row in range(total):
            item = self.table.item(row, VALIDITY_COL_EMPLOYEE)
            haystack = ""
            if item is not None:
                haystack = " ".join(str(item.data(ROLE_SEARCH) or "").casefold().split())
            match = needle in haystack if needle else True
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1
        return visible, total

    def _fill_state_filter(self) -> None:
        self.state_filter.clear()
        self.state_filter.addItem(EXAM_VALIDITY_FILTER_ALL_STATES, None)
        for code in EXAM_VALIDITY_STATE_ORDER:
            self.state_filter.addItem(EXAM_VALIDITY_STATE_LABELS[code], code)

    def _reload_choice_filters(self, rows: list[ExamValidityRow]) -> None:
        workplace_id = self._selected_id(self.workplace_filter)
        test_id = self._selected_id(self.test_filter)
        workplaces: dict[int, str] = {}
        tests: dict[int, str] = {}
        for row in rows:
            if row.workplace_id is not None:
                workplaces[row.workplace_id] = row.workplace_name or str(row.workplace_id)
            label = row.test_name if row.test_active else f"{row.test_name} (neaktivní)"
            tests[row.test_definition_id] = label
        self._reloading_filters = True
        self.workplace_filter.clear()
        self.workplace_filter.addItem(EXAM_VALIDITY_FILTER_ALL_WORKPLACES, None)
        for key, name in sorted(workplaces.items(), key=lambda item: czech_sort_key(item[1])):
            self.workplace_filter.addItem(name, key)
        self.test_filter.clear()
        self.test_filter.addItem(EXAM_VALIDITY_FILTER_ALL_TESTS, None)
        for key, name in sorted(tests.items(), key=lambda item: czech_sort_key(item[1])):
            self.test_filter.addItem(name, key)
        self._restore_combo(self.workplace_filter, workplace_id)
        self._restore_combo(self.test_filter, test_id)
        self._reloading_filters = False

    def _restore_combo(self, combo: NoWheelComboBox, value: int | None) -> None:
        if value is None:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _selected_id(self, combo: NoWheelComboBox) -> int | None:
        data = combo.currentData()
        if data is None:
            return None
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def _selected_state(self) -> str | None:
        data = self.state_filter.currentData()
        if not data:
            return None
        return str(data)
