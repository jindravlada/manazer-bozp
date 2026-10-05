"""Agenda připravených zkoušek."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_edit_action_button,
    configure_new_action_button,
)
from core.widgets.filter_bar import FilterBar
from core.widgets.table_row_actions import install_table_row_actions
from core.widgets.table_selection import refresh_and_restore_selection
from core.widgets.table_utils import configure_table_columns
from moduly.testy.constants import (
    EXAM_ACTION_DETAIL,
    EXAM_ACTION_PREPARE,
    EXAM_COL_EMPLOYEE,
    EXAM_COL_ID,
    EXAM_COL_TEST,
    EXAM_SEARCH_PLACEHOLDER,
    MODULE_NAME,
)
from moduly.testy.sluzby.test_exam_service import test_exam_service
from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
from moduly.testy.ui.test_exam_prepare_dialog import TestExamPrepareDialog
from moduly.testy.ui.test_exam_table import TestExamTable

_ROLE_SEARCH = Qt.ItemDataRole.UserRole + 1


class TestExamsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.prepare_btn = QPushButton(EXAM_ACTION_PREPARE)
        configure_new_action_button(self.prepare_btn)
        self.detail_btn = QPushButton(EXAM_ACTION_DETAIL)
        configure_edit_action_button(self.detail_btn)
        self.detail_btn.setEnabled(False)
        toolbar.addWidget(self.prepare_btn)
        toolbar.addWidget(self.detail_btn)
        toolbar.addStretch()

        self.table = TestExamTable()
        configure_table_columns(self.table, "test_exams")
        self.text_filter = FilterBar(
            self.table,
            placeholder=EXAM_SEARCH_PLACEHOLDER,
            apply_fn=self._apply_search,
        )

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)

        self.prepare_btn.clicked.connect(self.prepare_exam)
        self.detail_btn.clicked.connect(self.open_selected)
        self.table.doubleClicked.connect(self.open_selected)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        install_table_row_actions(
            self.table,
            on_edit=self.open_selected,
            can_edit=lambda: self.detail_btn.isEnabled(),
        )
        self.refresh()

    def refresh(self) -> None:
        selected_id = self.table.selected_exam_id()
        self.table.load_exams(test_exam_service.list_exams())
        configure_table_columns(self.table, "test_exams")
        refresh_and_restore_selection(self.table, selected_id, id_column=EXAM_COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()

    def prepare_exam(self) -> None:
        dialog = TestExamPrepareDialog(self)
        if not dialog.exec():
            return
        self._reload(dialog.saved_exam_id)

    def open_selected(self) -> None:
        exam_id = self.table.selected_exam_id()
        if exam_id is None:
            return
        exam = test_exam_service.get_exam(exam_id)
        if exam is None:
            QMessageBox.warning(self, MODULE_NAME, "Zkouška nebyla nalezena.")
            self.refresh()
            return
        dialog = TestExamDetailDialog(self, exam_id=exam.id)
        dialog.exec()

    def _reload(self, exam_id: int | None) -> None:
        self.table.load_exams(test_exam_service.list_exams())
        configure_table_columns(self.table, "test_exams")
        refresh_and_restore_selection(self.table, exam_id, id_column=EXAM_COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()

    def _apply_search(self, text: str) -> tuple[int, int]:
        needle = text.casefold()
        total = self.table.rowCount()
        visible = 0
        for row in range(total):
            item = self.table.item(row, EXAM_COL_EMPLOYEE)
            haystack = str(item.data(_ROLE_SEARCH) or "") if item is not None else ""
            test_item = self.table.item(row, EXAM_COL_TEST)
            if test_item is not None:
                haystack = f"{haystack} {test_item.text()}"
            match = needle in haystack.casefold() if needle else True
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1
        return visible, total

    def _update_action_buttons(self) -> None:
        self.detail_btn.setEnabled(self.table.selected_exam_id() is not None)
