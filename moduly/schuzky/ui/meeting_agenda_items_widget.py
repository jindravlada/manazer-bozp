"""Integrovaný seznam a editor bodů jednání."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from moduly.schuzky.constants import (
    ACTION_ADD_AGENDA_ITEM,
    ACTION_MOVE_DOWN,
    ACTION_MOVE_UP,
    ACTION_REMOVE,
    AGENDA_ITEMS_EMPTY,
    AGENDA_ITEMS_SECTION,
    AGENDA_SELECT_ITEM_MESSAGE,
    DIALOG_WINDOW_TITLE,
)
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service


def _plain_text_edit(*, placeholder: str, min_height: int) -> QTextEdit:
    edit = QTextEdit()
    edit.setPlaceholderText(placeholder)
    edit.setAcceptRichText(False)
    edit.setMinimumHeight(min_height)
    return edit


def _empty_item(*, display_order: int = 10) -> dict:
    return {
        "title": "",
        "moje_sdeleni": "",
        "prubeh_jednani": "",
        "zaver": "",
        "display_order": display_order,
    }


class MeetingAgendaItemsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[dict] = []
        self._current_index: int | None = None
        self._suppress_selection = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(AGENDA_ITEMS_SECTION)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton(ACTION_ADD_AGENDA_ITEM)
        self.remove_btn = QPushButton(ACTION_REMOVE)
        self.up_btn = QPushButton(ACTION_MOVE_UP)
        self.down_btn = QPushButton(ACTION_MOVE_DOWN)
        for button in (self.add_btn, self.remove_btn, self.up_btn, self.down_btn):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        left_layout.addLayout(toolbar)

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
        left_layout.addWidget(self.table, 1)

        self.empty_label = QLabel(AGENDA_ITEMS_EMPTY)
        self.empty_label.setWordWrap(True)
        left_layout.addWidget(self.empty_label)

        self.editor_panel = QWidget()
        editor_layout = QVBoxLayout(self.editor_panel)
        editor_layout.setContentsMargins(8, 0, 0, 0)
        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Název tématu")
        self.moje_sdeleni_edit = _plain_text_edit(
            placeholder="Moje sdělení",
            min_height=110,
        )
        self.prubeh_jednani_edit = _plain_text_edit(
            placeholder="Průběh jednání",
            min_height=150,
        )
        self.zaver_edit = _plain_text_edit(
            placeholder="Závěr",
            min_height=110,
        )

        form.addRow("Název tématu:", self.title_edit)
        form.addRow("Moje sdělení:", self.moje_sdeleni_edit)
        form.addRow("Průběh jednání:", self.prubeh_jednani_edit)
        form.addRow("Závěr:", self.zaver_edit)
        editor_layout.addLayout(form)
        editor_layout.addStretch(1)

        splitter.addWidget(left)
        splitter.addWidget(self.editor_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([280, 420])
        layout.addWidget(splitter, 1)

        self.add_btn.clicked.connect(self.add_item)
        self.remove_btn.clicked.connect(self.remove_item)
        self.up_btn.clicked.connect(lambda: self.move_item(-1))
        self.down_btn.clicked.connect(lambda: self.move_item(1))
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.title_edit.textChanged.connect(self._on_title_edited)

        self._set_editor_enabled(False)
        self._refresh_table()

    def load_for_meeting(self, meeting_id: int | None) -> None:
        self._flush_editor_to_item()
        self._items = []
        if meeting_id is not None:
            for item in meeting_agenda_item_service.get_for_meeting(meeting_id):
                self._items.append(meeting_agenda_item_service.item_to_dict(item))
        self._current_index = None
        self._refresh_table(select_row=0 if self._items else None)

    def get_items(self) -> list[dict]:
        self._flush_editor_to_item()
        return [dict(item) for item in self._items]

    def add_item(self) -> None:
        self._flush_editor_to_item()
        self._items.append(_empty_item(display_order=(len(self._items) + 1) * 10))
        new_index = len(self._items) - 1
        self._refresh_table(select_row=new_index)
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def remove_item(self) -> None:
        index = self._selected_index()
        if index is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, AGENDA_SELECT_ITEM_MESSAGE)
            return
        self._flush_editor_to_item()
        del self._items[index]
        if not self._items:
            self._current_index = None
            self._refresh_table(select_row=None)
            return
        next_index = min(index, len(self._items) - 1)
        self._refresh_table(select_row=next_index)

    def move_item(self, direction: int) -> None:
        index = self._selected_index()
        if index is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, AGENDA_SELECT_ITEM_MESSAGE)
            return
        target = index + direction
        if target < 0 or target >= len(self._items):
            return
        self._flush_editor_to_item()
        self._items[index], self._items[target] = self._items[target], self._items[index]
        self._refresh_table(select_row=target)

    def _on_selection_changed(self) -> None:
        if self._suppress_selection:
            return
        new_index = self._selected_index()
        if new_index == self._current_index:
            return
        self._flush_editor_to_item()
        self._current_index = new_index
        self._load_editor_from_item()

    def _on_title_edited(self, text: str) -> None:
        if self._suppress_selection or self._current_index is None:
            return
        if not (0 <= self._current_index < len(self._items)):
            return
        self._items[self._current_index]["title"] = text
        cell = self.table.item(self._current_index, 1)
        if cell is not None:
            cell.setText(text)

    def _selected_index(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _flush_editor_to_item(self) -> None:
        if self._current_index is None:
            return
        if not (0 <= self._current_index < len(self._items)):
            return
        self._items[self._current_index].update(
            {
                "title": self.title_edit.text().strip(),
                "moje_sdeleni": self.moje_sdeleni_edit.toPlainText(),
                "prubeh_jednani": self.prubeh_jednani_edit.toPlainText(),
                "zaver": self.zaver_edit.toPlainText(),
            }
        )
        cell = self.table.item(self._current_index, 1)
        if cell is not None:
            cell.setText(self._items[self._current_index]["title"])

    def _load_editor_from_item(self) -> None:
        if self._current_index is None or not (
            0 <= self._current_index < len(self._items)
        ):
            self._clear_editor()
            return

        item = self._items[self._current_index]
        self._suppress_selection = True
        self.title_edit.setText(item.get("title") or "")
        self.moje_sdeleni_edit.setPlainText(item.get("moje_sdeleni") or "")
        self.prubeh_jednani_edit.setPlainText(item.get("prubeh_jednani") or "")
        self.zaver_edit.setPlainText(item.get("zaver") or "")
        self._suppress_selection = False
        self._set_editor_enabled(True)

    def _clear_editor(self) -> None:
        self._suppress_selection = True
        self.title_edit.clear()
        self.moje_sdeleni_edit.clear()
        self.prubeh_jednani_edit.clear()
        self.zaver_edit.clear()
        self._suppress_selection = False
        self._set_editor_enabled(False)

    def _set_editor_enabled(self, enabled: bool) -> None:
        self.editor_panel.setEnabled(enabled)

    def _refresh_table(self, *, select_row: int | None = None) -> None:
        for index, item in enumerate(self._items):
            item["display_order"] = (index + 1) * 10

        self._suppress_selection = True
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("title") or ""))

        has_items = bool(self._items)
        self.empty_label.setVisible(not has_items)
        self.table.setVisible(True)

        if select_row is None or not has_items:
            self.table.clearSelection()
            self._current_index = None
            self._suppress_selection = False
            self._clear_editor()
            return

        select_row = max(0, min(select_row, len(self._items) - 1))
        self.table.selectRow(select_row)
        self._current_index = select_row
        self._suppress_selection = False
        self._load_editor_from_item()
