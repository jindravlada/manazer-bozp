"""Agenda definic Testů."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.export import open_export_file
from core.services.storage_service import storage_service
from core.widgets.dialog_utils import (
    configure_edit_action_button,
    configure_new_action_button,
    configure_perform_action_button,
    exec_maximized,
)
from core.widgets.filter_bar import FilterBar
from core.widgets.table_row_actions import install_table_row_actions
from core.widgets.table_selection import refresh_and_restore_selection
from core.widgets.table_utils import configure_table_columns
from moduly.testy.constants import (
    ACTION_EDIT,
    MODULE_NAME,
    SHOW_INACTIVE_LABEL,
    STUDY_QUESTIONS_ACTION,
    STUDY_QUESTIONS_EMPTY,
    STUDY_QUESTIONS_TITLE,
    TEST_ACTION_NEW,
    TEST_COL_ID,
    TEST_COL_NAME,
    TEST_SEARCH_PLACEHOLDER,
)
from moduly.testy.sluzby.study_questions_export_service import (
    StudyQuestionsError,
    study_questions_export_service,
)
from moduly.testy.sluzby.test_definition_service import test_definition_service
from moduly.testy.ui.test_definition_dialog import TestDefinitionDialog
from moduly.testy.ui.test_definition_table import TestDefinitionTable

_ROLE_DESCRIPTION = Qt.ItemDataRole.UserRole + 1


class TestDefinitionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(TEST_ACTION_NEW)
        configure_new_action_button(self.new_btn)
        self.edit_btn = QPushButton(ACTION_EDIT)
        configure_edit_action_button(self.edit_btn)
        self.edit_btn.setEnabled(False)
        self.study_btn = QPushButton(STUDY_QUESTIONS_ACTION)
        self.study_btn.setObjectName("study-questions-button")
        configure_perform_action_button(self.study_btn)
        self.study_btn.setEnabled(False)
        self.show_inactive = QCheckBox(SHOW_INACTIVE_LABEL)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.study_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.show_inactive)

        self.table = TestDefinitionTable()
        configure_table_columns(self.table, "test_definitions")
        self.text_filter = FilterBar(
            self.table,
            placeholder=TEST_SEARCH_PLACEHOLDER,
            apply_fn=self._apply_search,
        )

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)

        self.new_btn.clicked.connect(self.new_test)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.study_btn.clicked.connect(self.print_study_questions)
        self.show_inactive.toggled.connect(self.refresh)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        install_table_row_actions(
            self.table,
            on_edit=self.edit_selected,
            can_edit=lambda: self.edit_btn.isEnabled(),
        )
        self.refresh()

    def refresh(self) -> None:
        selected_id = self.table.selected_test_id()
        tests = test_definition_service.list_tests(
            include_inactive=self.show_inactive.isChecked(),
        )
        self.table.load_tests(tests)
        configure_table_columns(self.table, "test_definitions")
        refresh_and_restore_selection(self.table, selected_id, id_column=TEST_COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()

    def new_test(self) -> None:
        dialog = TestDefinitionDialog(self)
        if not exec_maximized(dialog):
            return
        self._reload(dialog.saved_test_id)

    def edit_selected(self) -> None:
        test_id = self.table.selected_test_id()
        if test_id is None:
            return
        test = test_definition_service.get_test(test_id)
        if test is None:
            QMessageBox.warning(self, MODULE_NAME, "Test nebyl nalezen.")
            self.refresh()
            return
        dialog = TestDefinitionDialog(self, test=test)
        if not exec_maximized(dialog):
            return
        self._reload(dialog.saved_test_id)

    def _reload(self, test_id: int | None) -> None:
        tests = test_definition_service.list_tests(
            include_inactive=self.show_inactive.isChecked(),
        )
        self.table.load_tests(tests)
        configure_table_columns(self.table, "test_definitions")
        refresh_and_restore_selection(self.table, test_id, id_column=TEST_COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()

    def _apply_search(self, text: str) -> tuple[int, int]:
        needle = text.casefold()
        total = self.table.rowCount()
        visible = 0
        for row in range(total):
            item = self.table.item(row, TEST_COL_NAME)
            name = item.text() if item is not None else ""
            description = ""
            if item is not None:
                description = str(item.data(_ROLE_DESCRIPTION) or "")
            match = needle in f"{name} {description}".casefold() if needle else True
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1
        return visible, total

    def print_study_questions(self) -> None:
        test_id = self.table.selected_test_id()
        if test_id is None:
            self._update_action_buttons()
            return
        test = test_definition_service.get_test(test_id)
        if test is None:
            QMessageBox.warning(self, MODULE_NAME, "Test nebyl nalezen.")
            self.refresh()
            return
        try:
            material = study_questions_export_service.collect(test.id)
        except StudyQuestionsError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        if not material.has_questions:
            QMessageBox.warning(self, MODULE_NAME, STUDY_QUESTIONS_EMPTY)
            return
        default_path = storage_service.exports_dir / study_questions_export_service.filename(
            test.name
        )
        chosen, _selected_filter = QFileDialog.getSaveFileName(
            self,
            STUDY_QUESTIONS_TITLE,
            str(default_path),
            "OpenDocument (*.odt)",
        )
        if not chosen:
            return
        try:
            path = study_questions_export_service.export(test.id, Path(chosen))
        except StudyQuestionsError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        open_export_file(path, parent=self, title=STUDY_QUESTIONS_TITLE)
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        selected = self.table.selected_test_id() is not None
        self.edit_btn.setEnabled(selected)
        self.study_btn.setEnabled(selected)
