"""Seznam bodů jednání v editoru schůzky."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moduly.schuzky.constants import (
    ACTION_ADD_AGENDA_ITEM,
    ACTION_EDIT,
    ACTION_MOVE_DOWN,
    ACTION_MOVE_UP,
    ACTION_REMOVE,
    AGENDA_ITEMS_EMPTY,
    AGENDA_ITEMS_SECTION,
    AGENDA_SELECT_ITEM_MESSAGE,
    DIALOG_WINDOW_TITLE,
)
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.ui.meeting_agenda_item_dialog import MeetingAgendaItemDialog


class MeetingAgendaItemsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(AGENDA_ITEMS_SECTION)
        layout.addWidget(header)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton(ACTION_ADD_AGENDA_ITEM)
        self.edit_btn = QPushButton(ACTION_EDIT)
        self.remove_btn = QPushButton(ACTION_REMOVE)
        self.up_btn = QPushButton(ACTION_MOVE_UP)
        self.down_btn = QPushButton(ACTION_MOVE_DOWN)
        for button in (
            self.add_btn,
            self.edit_btn,
            self.remove_btn,
            self.up_btn,
            self.down_btn,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Pořadí", "Název tématu"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        self.empty_label = QLabel(AGENDA_ITEMS_EMPTY)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.add_btn.clicked.connect(self.add_item)
        self.edit_btn.clicked.connect(self.edit_item)
        self.remove_btn.clicked.connect(self.remove_item)
        self.up_btn.clicked.connect(lambda: self.move_item(-1))
        self.down_btn.clicked.connect(lambda: self.move_item(1))
        self.table.doubleClicked.connect(self.edit_item)

        self._refresh_table()

    def load_for_meeting(self, meeting_id: int | None) -> None:
        self._items = []
        if meeting_id is not None:
            for item in meeting_agenda_item_service.get_for_meeting(meeting_id):
                self._items.append(meeting_agenda_item_service.item_to_dict(item))
        self._refresh_table()

    def get_items(self) -> list[dict]:
        return [dict(item) for item in self._items]

    def add_item(self) -> None:
        dialog = MeetingAgendaItemDialog(self)
        if not dialog.exec():
            return
        data = dialog.get_data()
        self._items.append(
            {
                "title": data["title"],
                "display_order": (len(self._items) + 1) * 10,
            }
        )
        self._refresh_table()
        self.table.selectRow(len(self._items) - 1)

    def edit_item(self) -> None:
        index = self._selected_index()
        if index is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, AGENDA_SELECT_ITEM_MESSAGE)
            return
        dialog = MeetingAgendaItemDialog(self, item=self._items[index])
        if not dialog.exec():
            return
        data = dialog.get_data()
        self._items[index] = {
            **self._items[index],
            "title": data["title"],
        }
        self._refresh_table()
        self.table.selectRow(index)

    def remove_item(self) -> None:
        index = self._selected_index()
        if index is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, AGENDA_SELECT_ITEM_MESSAGE)
            return
        del self._items[index]
        self._refresh_table()

    def move_item(self, direction: int) -> None:
        index = self._selected_index()
        if index is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, AGENDA_SELECT_ITEM_MESSAGE)
            return
        target = index + direction
        if target < 0 or target >= len(self._items):
            return
        self._items[index], self._items[target] = self._items[target], self._items[index]
        self._refresh_table()
        self.table.selectRow(target)

    def _selected_index(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _refresh_table(self) -> None:
        for index, item in enumerate(self._items):
            item["display_order"] = (index + 1) * 10

        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            order_item = QTableWidgetItem(str(row + 1))
            title_item = QTableWidgetItem(item.get("title") or "")
            self.table.setItem(row, 0, order_item)
            self.table.setItem(row, 1, title_item)

        has_items = bool(self._items)
        self.empty_label.setVisible(not has_items)
        self.table.setVisible(has_items)
