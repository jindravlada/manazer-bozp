"""Agenda okruhů písemných otázek."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
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
    ACTION_EDIT,
    MODULE_NAME,
    SHOW_INACTIVE_LABEL,
    TOPIC_ACTION_NEW,
    TOPIC_COL_ID,
    TOPIC_SEARCH_PLACEHOLDER,
)
from moduly.testy.sluzby.written_question_topic_service import (
    written_question_topic_service,
)
from moduly.testy.ui.written_question_topic_dialog import WrittenQuestionTopicDialog
from moduly.testy.ui.written_question_topic_table import WrittenQuestionTopicTable


class WrittenQuestionTopicsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(TOPIC_ACTION_NEW)
        configure_new_action_button(self.new_btn)
        self.edit_btn = QPushButton(ACTION_EDIT)
        configure_edit_action_button(self.edit_btn)
        self.edit_btn.setEnabled(False)
        self.show_inactive = QCheckBox(SHOW_INACTIVE_LABEL)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.show_inactive)

        self.table = WrittenQuestionTopicTable()
        configure_table_columns(self.table, "written_question_topics")
        self.text_filter = FilterBar(self.table, placeholder=TOPIC_SEARCH_PLACEHOLDER)

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)

        self.new_btn.clicked.connect(self.new_topic)
        self.edit_btn.clicked.connect(self.edit_selected)
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
        selected_id = self.table.selected_topic_id()
        topics = written_question_topic_service.list_topics(
            include_inactive=self.show_inactive.isChecked(),
        )
        self.table.load_topics(topics)
        configure_table_columns(self.table, "written_question_topics")
        refresh_and_restore_selection(self.table, selected_id, id_column=TOPIC_COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()

    def new_topic(self) -> None:
        dialog = WrittenQuestionTopicDialog(self)
        if not dialog.exec():
            return
        self._reload(dialog.saved_topic_id)

    def edit_selected(self) -> None:
        topic_id = self.table.selected_topic_id()
        if topic_id is None:
            return
        topic = written_question_topic_service.get_topic(topic_id)
        if topic is None:
            QMessageBox.warning(self, MODULE_NAME, "Okruh nebyl nalezen.")
            self.refresh()
            return
        dialog = WrittenQuestionTopicDialog(self, topic=topic)
        if not dialog.exec():
            return
        self._reload(dialog.saved_topic_id)

    def _reload(self, topic_id: int | None) -> None:
        topics = written_question_topic_service.list_topics(
            include_inactive=self.show_inactive.isChecked(),
        )
        self.table.load_topics(topics)
        configure_table_columns(self.table, "written_question_topics")
        refresh_and_restore_selection(self.table, topic_id, id_column=TOPIC_COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        self.edit_btn.setEnabled(self.table.selected_topic_id() is not None)
