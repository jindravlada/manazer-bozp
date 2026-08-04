"""Integrovaný seznam a editor bodů jednání včetně úkolů bodu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
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
    ACTION_ADD_TASK,
    ACTION_MOVE_DOWN,
    ACTION_MOVE_UP,
    ACTION_OPEN_TASK,
    ACTION_REMOVE,
    ACTION_UNLINK_TASK,
    AGENDA_ITEMS_EMPTY,
    AGENDA_ITEMS_SECTION,
    AGENDA_SELECT_ITEM_MESSAGE,
    DIALOG_WINDOW_TITLE,
    SAVE_MEETING_BEFORE_TASK_MESSAGE,
    SECTION_ITEM_TASKS,
)
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.sluzby.meeting_item_task_service import meeting_item_task_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog


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


def _format_due(due_date) -> str:
    if due_date is None:
        return "—"
    return f"{due_date.day}. {due_date.month}. {due_date.year}"


class MeetingAgendaItemsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[dict] = []
        self._meeting_id: int | None = None
        self._current_index: int | None = None
        self._suppress_selection = False
        self._task_ids: list[int] = []

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
            min_height=90,
        )
        self.prubeh_jednani_edit = _plain_text_edit(
            placeholder="Průběh jednání",
            min_height=110,
        )
        self.zaver_edit = _plain_text_edit(
            placeholder="Závěr",
            min_height=90,
        )

        form.addRow("Název tématu:", self.title_edit)
        form.addRow("Moje sdělení:", self.moje_sdeleni_edit)
        form.addRow("Průběh jednání:", self.prubeh_jednani_edit)
        form.addRow("Závěr:", self.zaver_edit)
        editor_layout.addLayout(form)

        tasks_header = QLabel(SECTION_ITEM_TASKS)
        header_font = tasks_header.font()
        header_font.setBold(True)
        tasks_header.setFont(header_font)
        editor_layout.addWidget(tasks_header)

        tasks_toolbar = QHBoxLayout()
        self.add_task_btn = QPushButton(ACTION_ADD_TASK)
        self.open_task_btn = QPushButton(ACTION_OPEN_TASK)
        self.unlink_task_btn = QPushButton(ACTION_UNLINK_TASK)
        for button in (self.add_task_btn, self.open_task_btn, self.unlink_task_btn):
            tasks_toolbar.addWidget(button)
        tasks_toolbar.addStretch(1)
        editor_layout.addLayout(tasks_toolbar)

        self.tasks_table = QTableWidget(0, 4)
        self.tasks_table.setHorizontalHeaderLabels(
            ["Název", "Odpovědná osoba", "Termín", "Stav"]
        )
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tasks_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tasks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tasks_table.setAlternatingRowColors(True)
        self.tasks_table.verticalHeader().setVisible(False)
        tasks_header_view = self.tasks_table.horizontalHeader()
        tasks_header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tasks_header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tasks_header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tasks_header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tasks_table.setMinimumHeight(140)
        editor_layout.addWidget(self.tasks_table, 1)

        splitter.addWidget(left)
        splitter.addWidget(self.editor_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([280, 460])
        layout.addWidget(splitter, 1)

        self.add_btn.clicked.connect(self.add_item)
        self.remove_btn.clicked.connect(self.remove_item)
        self.up_btn.clicked.connect(lambda: self.move_item(-1))
        self.down_btn.clicked.connect(lambda: self.move_item(1))
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.title_edit.textChanged.connect(self._on_title_edited)
        self.add_task_btn.clicked.connect(self.add_task)
        self.open_task_btn.clicked.connect(self.open_selected_task)
        self.unlink_task_btn.clicked.connect(self.unlink_selected_task)
        self.tasks_table.doubleClicked.connect(self.open_selected_task)
        self.tasks_table.itemSelectionChanged.connect(self._update_task_buttons)

        self._set_editor_enabled(False)
        self._refresh_table()

    def load_for_meeting(self, meeting_id: int | None) -> None:
        self._flush_editor_to_item()
        self._meeting_id = meeting_id
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

    def add_task(self) -> None:
        meeting_id, item_id = self._current_meeting_and_item_ids()
        if meeting_id is None or item_id is None:
            QMessageBox.information(
                self,
                DIALOG_WINDOW_TITLE,
                SAVE_MEETING_BEFORE_TASK_MESSAGE,
            )
            return

        dialog = TaskDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        title = (data.get("title") or "").strip()
        if not title:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Zadejte název úkolu.")
            return

        meeting_item_task_service.create_for_item(
            meeting_id=meeting_id,
            item_id=item_id,
            title=title,
            description=data.get("description") or "",
            priority=data.get("priority") or "Normální",
            due_date=data.get("due_date"),
            responsible_person_id=data.get("responsible_person_id"),
            workplace_id=data.get("workplace_id"),
            completed=bool(data.get("completed")),
            completed_date=data.get("completed_date"),
            check_due_date=data.get("check_due_date"),
            checked_date=data.get("checked_date"),
            checked_by_id=data.get("checked_by_id"),
            canceled=bool(data.get("canceled")),
            note=data.get("note") or "",
            requires_verification=data.get("requires_verification"),
        )
        self._refresh_tasks()

    def open_selected_task(self) -> None:
        task_id = self._selected_task_id()
        if task_id is None:
            return
        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, "Úkol nebyl nalezen.")
            self._refresh_tasks()
            return
        dialog = TaskDialog(self, task=task)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            task_service.update_task(task_id, **dialog.get_data())
        self._refresh_tasks()

    def unlink_selected_task(self) -> None:
        task_id = self._selected_task_id()
        if task_id is None:
            return
        meeting_item_task_service.unlink_task(task_id)
        self._refresh_tasks()

    def _current_meeting_and_item_ids(self) -> tuple[int | None, int | None]:
        if self._meeting_id is None or self._current_index is None:
            return None, None
        if not (0 <= self._current_index < len(self._items)):
            return None, None
        item_id = self._items[self._current_index].get("id")
        if item_id is None:
            return self._meeting_id, None
        try:
            return self._meeting_id, int(item_id)
        except (TypeError, ValueError):
            return self._meeting_id, None

    def _selected_task_id(self) -> int | None:
        rows = self.tasks_table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row < 0 or row >= len(self._task_ids):
            return None
        return self._task_ids[row]

    def _update_task_buttons(self) -> None:
        has_selection = self._selected_task_id() is not None
        self.open_task_btn.setEnabled(has_selection)
        self.unlink_task_btn.setEnabled(has_selection)

    def _refresh_tasks(self) -> None:
        self.tasks_table.setRowCount(0)
        self._task_ids = []
        meeting_id, item_id = self._current_meeting_and_item_ids()
        if meeting_id is None or item_id is None:
            self._update_task_buttons()
            return

        tasks = meeting_item_task_service.list_for_item(meeting_id, item_id)
        self.tasks_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            self._task_ids.append(task.id)
            self.tasks_table.setItem(row, 0, QTableWidgetItem(task.title or ""))
            self.tasks_table.setItem(
                row,
                1,
                QTableWidgetItem(task.responsible_person or "—"),
            )
            self.tasks_table.setItem(row, 2, QTableWidgetItem(_format_due(task.due_date)))
            status = getattr(task, "computed_status", None) or task.status or ""
            self.tasks_table.setItem(row, 3, QTableWidgetItem(status))
        self._update_task_buttons()

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
        self._refresh_tasks()

    def _clear_editor(self) -> None:
        self._suppress_selection = True
        self.title_edit.clear()
        self.moje_sdeleni_edit.clear()
        self.prubeh_jednani_edit.clear()
        self.zaver_edit.clear()
        self._suppress_selection = False
        self.tasks_table.setRowCount(0)
        self._task_ids = []
        self._set_editor_enabled(False)
        self._update_task_buttons()

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
