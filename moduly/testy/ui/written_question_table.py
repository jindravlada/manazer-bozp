"""Tabulka banky písemných otázek."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_text,
)
from moduly.testy.constants import (
    ANSWER_KIND_IMAGE,
    ANSWER_KIND_IMAGE_LABEL,
    ANSWER_KIND_TEXT_LABEL,
    QUESTION_COL_ID,
    QUESTION_COL_KIND,
    QUESTION_COL_STATUS,
    QUESTION_COL_TEXT,
    QUESTION_COL_TOPIC,
    QUESTION_COLUMN_HEADERS,
    STATUS_ACTIVE_LABEL,
    STATUS_INACTIVE_LABEL,
)
from moduly.testy.modely.written_question import WrittenQuestion
from moduly.testy.sluzby.written_question_topic_service import (
    written_question_topic_service,
)

_ROLE_ID = Qt.ItemDataRole.UserRole


class WrittenQuestionTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(QUESTION_COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(QUESTION_COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setColumnHidden(QUESTION_COL_ID, True)
        enable_typed_sorting(self)

    def selected_question_id(self) -> int | None:
        rows = self.selectionModel().selectedRows() if self.selectionModel() else []
        if len(rows) != 1:
            return None
        item = self.item(rows[0].row(), QUESTION_COL_ID)
        if item is None:
            return None
        raw = item.data(_ROLE_ID)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def load_questions(self, questions: list[WrittenQuestion]) -> None:
        with sorting_paused(self):
            self.setRowCount(len(questions))
            for row, question in enumerate(questions):
                topic = written_question_topic_service.get_topic(question.topic_id)
                if topic is None:
                    topic_name = ""
                elif topic.active:
                    topic_name = topic.name
                else:
                    topic_name = f"{topic.name} (neaktivní)"
                kind = (
                    ANSWER_KIND_IMAGE_LABEL
                    if question.answer_kind == ANSWER_KIND_IMAGE
                    else ANSWER_KIND_TEXT_LABEL
                )
                status = STATUS_ACTIVE_LABEL if question.active else STATUS_INACTIVE_LABEL
                values = {
                    QUESTION_COL_ID: str(question.id),
                    QUESTION_COL_TEXT: " ".join(question.text.split()),
                    QUESTION_COL_TOPIC: topic_name,
                    QUESTION_COL_KIND: kind,
                    QUESTION_COL_STATUS: status,
                }
                for column, text in values.items():
                    item = create_typed_item(
                        text,
                        typed_text(text),
                        stable_id=question.id,
                    )
                    item.setData(_ROLE_ID, question.id)
                    self.setItem(row, column, item)
