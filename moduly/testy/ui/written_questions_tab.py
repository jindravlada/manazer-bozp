"""Agenda banky písemných otázek."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
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
from core.widgets.no_wheel_guards import NoWheelComboBox
from core.widgets.table_row_actions import install_table_row_actions
from core.widgets.table_selection import refresh_and_restore_selection
from core.widgets.table_utils import configure_table_columns
from moduly.testy.constants import (
    ACTION_EDIT,
    MODULE_NAME,
    QUESTION_ACTION_NEW,
    QUESTION_COL_ID,
    QUESTION_SEARCH_PLACEHOLDER,
    QUESTION_TOPIC_FILTER_ALL,
    SHOW_INACTIVE_LABEL,
)
from moduly.testy.sluzby.written_question_service import written_question_service
from moduly.testy.sluzby.written_question_topic_service import (
    written_question_topic_service,
)
from moduly.testy.ui.written_question_dialog import WrittenQuestionDialog
from moduly.testy.ui.written_question_table import WrittenQuestionTable


class WrittenQuestionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._reloading_topics = False

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(QUESTION_ACTION_NEW)
        configure_new_action_button(self.new_btn)
        self.edit_btn = QPushButton(ACTION_EDIT)
        configure_edit_action_button(self.edit_btn)
        self.edit_btn.setEnabled(False)
        self.show_inactive = QCheckBox(SHOW_INACTIVE_LABEL)
        self.topic_filter = NoWheelComboBox()
        self.topic_filter.setMinimumWidth(220)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(QLabel("Okruh:"))
        toolbar.addWidget(self.topic_filter)
        toolbar.addStretch()
        toolbar.addWidget(self.show_inactive)

        self.table = WrittenQuestionTable()
        configure_table_columns(self.table, "written_questions")
        self.text_filter = FilterBar(self.table, placeholder=QUESTION_SEARCH_PLACEHOLDER)

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)

        self.new_btn.clicked.connect(self.new_question)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.show_inactive.toggled.connect(self.refresh)
        self.topic_filter.currentIndexChanged.connect(self._on_topic_filter_changed)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        install_table_row_actions(
            self.table,
            on_edit=self.edit_selected,
            can_edit=lambda: self.edit_btn.isEnabled(),
        )
        self.refresh()

    def refresh(self) -> None:
        selected_id = self.table.selected_question_id()
        self._reload_topic_filter()
        questions = written_question_service.list_questions(
            include_inactive=self.show_inactive.isChecked(),
            topic_id=self._topic_filter_id(),
        )
        self.table.load_questions(questions)
        configure_table_columns(self.table, "written_questions")
        refresh_and_restore_selection(self.table, selected_id, id_column=QUESTION_COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()

    def new_question(self) -> None:
        dialog = WrittenQuestionDialog(self)
        if not dialog.exec():
            return
        self._reload(dialog.saved_question_id)

    def edit_selected(self) -> None:
        question_id = self.table.selected_question_id()
        if question_id is None:
            return
        question = written_question_service.get_question(question_id)
        if question is None:
            QMessageBox.warning(self, MODULE_NAME, "Otázka nebyla nalezena.")
            self.refresh()
            return
        dialog = WrittenQuestionDialog(self, question=question)
        if not dialog.exec():
            return
        self._reload(dialog.saved_question_id)

    def _reload(self, question_id: int | None) -> None:
        self._reload_topic_filter()
        questions = written_question_service.list_questions(
            include_inactive=self.show_inactive.isChecked(),
            topic_id=self._topic_filter_id(),
        )
        self.table.load_questions(questions)
        configure_table_columns(self.table, "written_questions")
        refresh_and_restore_selection(self.table, question_id, id_column=QUESTION_COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()

    def _on_topic_filter_changed(self) -> None:
        if self._reloading_topics:
            return
        self.refresh()

    def _topic_filter_id(self) -> int | None:
        data = self.topic_filter.currentData()
        if data is None:
            return None
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def _reload_topic_filter(self) -> None:
        selected = self._topic_filter_id()
        self._reloading_topics = True
        self.topic_filter.clear()
        self.topic_filter.addItem(QUESTION_TOPIC_FILTER_ALL, None)
        for topic in written_question_topic_service.list_topics(include_inactive=True):
            label = topic.name if topic.active else f"{topic.name} (neaktivní)"
            self.topic_filter.addItem(label, int(topic.id))
        if selected is not None:
            index = self.topic_filter.findData(selected)
            if index >= 0:
                self.topic_filter.setCurrentIndex(index)
        self._reloading_topics = False

    def _update_action_buttons(self) -> None:
        self.edit_btn.setEnabled(self.table.selected_question_id() is not None)
