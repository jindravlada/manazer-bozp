"""Tabulka ústních okruhů."""

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
    STATUS_ACTIVE_LABEL,
    STATUS_INACTIVE_LABEL,
    TOPIC_COL_DESCRIPTION,
    TOPIC_COL_ID,
    TOPIC_COL_NAME,
    TOPIC_COL_STATUS,
    TOPIC_COLUMN_HEADERS,
)
from moduly.testy.modely.oral_question_topic import OralQuestionTopic

_ROLE_ID = Qt.ItemDataRole.UserRole


class OralQuestionTopicTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(TOPIC_COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(TOPIC_COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setColumnHidden(TOPIC_COL_ID, True)
        enable_typed_sorting(self)

    def selected_topic_id(self) -> int | None:
        rows = self.selectionModel().selectedRows() if self.selectionModel() else []
        if len(rows) != 1:
            return None
        item = self.item(rows[0].row(), TOPIC_COL_ID)
        if item is None:
            return None
        raw = item.data(_ROLE_ID)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def load_topics(self, topics: list[OralQuestionTopic]) -> None:
        with sorting_paused(self):
            self.setRowCount(len(topics))
            for row, topic in enumerate(topics):
                status = STATUS_ACTIVE_LABEL if topic.active else STATUS_INACTIVE_LABEL
                description = " ".join((topic.description or "").split())
                values = {
                    TOPIC_COL_ID: str(topic.id),
                    TOPIC_COL_NAME: topic.name,
                    TOPIC_COL_DESCRIPTION: description,
                    TOPIC_COL_STATUS: status,
                }
                for column, text in values.items():
                    item = create_typed_item(
                        text,
                        typed_text(text),
                        stable_id=topic.id,
                    )
                    item.setData(_ROLE_ID, topic.id)
                    self.setItem(row, column, item)
