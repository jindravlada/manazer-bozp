"""Integrovaný seznam a editor bodů jednání včetně úkolů bodu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
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
    AGENDA_ITEM_NONE_SELECTED,
    AGENDA_ITEM_STATUS_ICONS,
    AGENDA_ITEM_STATUS_MENU_TITLE,
    AGENDA_ITEM_STATUSES,
    AGENDA_ITEMS_COUNT_TEMPLATE,
    AGENDA_ITEMS_EMPTY,
    AGENDA_SELECT_ITEM_MESSAGE,
    DEFAULT_AGENDA_ITEM_STATUS,
    DIALOG_WINDOW_TITLE,
    SAVE_MEETING_BEFORE_TASK_MESSAGE,
    SECTION_ITEM_TASKS,
)
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.sluzby.meeting_item_task_service import meeting_item_task_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog

_LIST_STYLE = """
QListWidget {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    outline: none;
    padding: 2px;
}
QListWidget::item {
    padding: 8px 10px;
    margin: 1px 0;
    border-radius: 3px;
}
QListWidget::item:selected {
    background: #dbeafe;
    color: #0f172a;
    border-left: 4px solid #2563eb;
    font-weight: 600;
}
QListWidget::item:hover:!selected {
    background: #f1f5f9;
}
"""


def _plain_text_edit(*, placeholder: str, min_height: int) -> QTextEdit:
    edit = QTextEdit()
    edit.setPlaceholderText(placeholder)
    edit.setAcceptRichText(False)
    edit.setMinimumHeight(min_height)
    return edit


def _empty_item(*, display_order: int = 10) -> dict:
    return {
        "title": "",
        "status": DEFAULT_AGENDA_ITEM_STATUS,
        "moje_sdeleni": "",
        "prubeh_jednani": "",
        "zaver": "",
        "display_order": display_order,
    }


def _status_icon(status: str | None) -> str:
    normalized = meeting_agenda_item_service.normalize_status(status)
    return AGENDA_ITEM_STATUS_ICONS.get(normalized, "🟡")


def _item_label(index: int, item: dict) -> str:
    icon = _status_icon(item.get("status"))
    title = (item.get("title") or "").strip() or "Bez názvu"
    return f"{icon} {index + 1}. {title}"


def _format_due(due_date) -> str:
    if due_date is None:
        return "—"
    return f"{due_date.day}. {due_date.month}. {due_date.year}"


class MeetingAgendaItemsWidget(QWidget):
    def __init__(self, parent=None, *, template_mode: bool = False):
        super().__init__(parent)
        self._template_mode = bool(template_mode)
        self._items: list[dict] = []
        self._meeting_id: int | None = None
        self._current_index: int | None = None
        self._suppress_selection = False
        self._task_ids: list[int] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.count_label = QLabel(AGENDA_ITEMS_COUNT_TEMPLATE.format(count=0))
        count_font = self.count_label.font()
        count_font.setBold(True)
        self.count_label.setFont(count_font)
        left_layout.addWidget(self.count_label)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton(ACTION_ADD_AGENDA_ITEM)
        self.remove_btn = QPushButton(ACTION_REMOVE)
        self.up_btn = QPushButton(ACTION_MOVE_UP)
        self.down_btn = QPushButton(ACTION_MOVE_DOWN)
        for button in (self.add_btn, self.remove_btn, self.up_btn, self.down_btn):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        left_layout.addLayout(toolbar)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.setStyleSheet(_LIST_STYLE)
        self.list_widget.setUniformItemSizes(True)
        # Zpětná kompatibilita testů (dříve QTableWidget).
        self.list_widget.selectRow = self.selectRow  # type: ignore[method-assign]
        self.table = self.list_widget
        left_layout.addWidget(self.list_widget, 1)

        self.empty_label = QLabel(AGENDA_ITEMS_EMPTY)
        self.empty_label.setWordWrap(True)
        left_layout.addWidget(self.empty_label)

        self.editor_stack = QStackedWidget()

        self.none_selected_label = QLabel(AGENDA_ITEM_NONE_SELECTED)
        self.none_selected_label.setWordWrap(True)
        self.none_selected_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.none_selected_label.setObjectName("MutedText")
        none_page = QWidget()
        none_layout = QVBoxLayout(none_page)
        none_layout.setContentsMargins(8, 0, 0, 0)
        none_layout.addWidget(self.none_selected_label)
        none_layout.addStretch(1)
        self.editor_stack.addWidget(none_page)

        self.editor_panel = QWidget()
        editor_layout = QVBoxLayout(self.editor_panel)
        editor_layout.setContentsMargins(8, 0, 0, 0)
        form = QFormLayout()

        self.status_combo = QComboBox()
        self.status_combo.addItems(list(AGENDA_ITEM_STATUSES))
        self.status_combo.setCurrentText(DEFAULT_AGENDA_ITEM_STATUS)

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

        form.addRow("Stav:", self.status_combo)
        form.addRow("Název tématu:", self.title_edit)
        form.addRow("Moje sdělení:", self.moje_sdeleni_edit)
        form.addRow("Průběh jednání:", self.prubeh_jednani_edit)
        form.addRow("Závěr:", self.zaver_edit)
        editor_layout.addLayout(form)

        self.tasks_header = QLabel(SECTION_ITEM_TASKS)
        header_font = self.tasks_header.font()
        header_font.setBold(True)
        self.tasks_header.setFont(header_font)
        editor_layout.addWidget(self.tasks_header)

        tasks_toolbar = QHBoxLayout()
        self.add_task_btn = QPushButton(ACTION_ADD_TASK)
        self.open_task_btn = QPushButton(ACTION_OPEN_TASK)
        self.unlink_task_btn = QPushButton(ACTION_UNLINK_TASK)
        for button in (self.add_task_btn, self.open_task_btn, self.unlink_task_btn):
            tasks_toolbar.addWidget(button)
        tasks_toolbar.addStretch(1)
        editor_layout.addLayout(tasks_toolbar)
        self._tasks_toolbar = tasks_toolbar

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

        self.editor_stack.addWidget(self.editor_panel)

        if self._template_mode:
            self._apply_template_mode(form)

        splitter.addWidget(left)
        splitter.addWidget(self.editor_stack)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([300, 460])
        layout.addWidget(splitter, 1)

        self.add_btn.clicked.connect(self.add_item)
        self.remove_btn.clicked.connect(self.remove_item)
        self.up_btn.clicked.connect(lambda: self.move_item(-1))
        self.down_btn.clicked.connect(lambda: self.move_item(1))
        self.list_widget.currentRowChanged.connect(self._on_current_row_changed)
        self.list_widget.customContextMenuRequested.connect(self._show_status_context_menu)
        self.title_edit.textChanged.connect(self._on_title_edited)
        self.status_combo.currentTextChanged.connect(self._on_status_edited)
        self.add_task_btn.clicked.connect(self.add_task)
        self.open_task_btn.clicked.connect(self.open_selected_task)
        self.unlink_task_btn.clicked.connect(self.unlink_selected_task)
        self.tasks_table.doubleClicked.connect(self.open_selected_task)
        self.tasks_table.itemSelectionChanged.connect(self._update_task_buttons)

        self._show_none_selected()
        self._refresh_list()

    def _apply_template_mode(self, form: QFormLayout) -> None:
        """Šablona: jen téma, Moje sdělení a výchozí stav – bez průběhu, závěru a úkolů."""
        form.labelForField(self.prubeh_jednani_edit).setVisible(False)
        self.prubeh_jednani_edit.setVisible(False)
        form.labelForField(self.zaver_edit).setVisible(False)
        self.zaver_edit.setVisible(False)
        self.tasks_header.setVisible(False)
        self.add_task_btn.setVisible(False)
        self.open_task_btn.setVisible(False)
        self.unlink_task_btn.setVisible(False)
        self.tasks_table.setVisible(False)

    def selectRow(self, row: int) -> None:
        """Kompatibilita se staršími testy (QTableWidget.selectRow)."""
        self.list_widget.setCurrentRow(row)

    def load_for_meeting(self, meeting_id: int | None) -> None:
        self._flush_editor_to_item()
        self._meeting_id = meeting_id
        self._items = []
        if meeting_id is not None:
            for item in meeting_agenda_item_service.get_for_meeting(meeting_id):
                self._items.append(meeting_agenda_item_service.item_to_dict(item))
        self._current_index = None
        self._refresh_list(select_row=0 if self._items else None)

    def load_items(self, items: list[dict] | None, *, meeting_id: int | None = None) -> None:
        """Načte body z dict (např. šablona) bez ID a vazeb na úkoly."""
        self._flush_editor_to_item()
        self._meeting_id = meeting_id
        self._items = []
        for index, raw in enumerate(items or []):
            self._items.append(
                {
                    "title": str(raw.get("title") or "").strip(),
                    "status": meeting_agenda_item_service.normalize_status(raw.get("status")),
                    "moje_sdeleni": str(raw.get("moje_sdeleni") or ""),
                    "prubeh_jednani": "",
                    "zaver": "",
                    "display_order": (index + 1) * 10,
                }
            )
        self._current_index = None
        self._refresh_list(select_row=0 if self._items else None)

    def get_items(self) -> list[dict]:
        self._flush_editor_to_item()
        if not self._template_mode:
            return [dict(item) for item in self._items]
        result: list[dict] = []
        for item in self._items:
            payload = dict(item)
            payload["prubeh_jednani"] = ""
            payload["zaver"] = ""
            result.append(payload)
        return result

    def add_item(self) -> None:
        self._flush_editor_to_item()
        self._items.append(_empty_item(display_order=(len(self._items) + 1) * 10))
        new_index = len(self._items) - 1
        self._refresh_list(select_row=new_index)
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
            self._refresh_list(select_row=None)
            return
        next_index = min(index, len(self._items) - 1)
        self._refresh_list(select_row=next_index)

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
        self._refresh_list(select_row=target)

    def add_task(self) -> None:
        meeting_id, item_id = self._current_meeting_and_item_ids()
        if meeting_id is None or item_id is None:
            QMessageBox.information(
                self,
                DIALOG_WINDOW_TITLE,
                SAVE_MEETING_BEFORE_TASK_MESSAGE,
            )
            return

        def _create_for_item(data: dict):
            return meeting_item_task_service.create_for_item(
                meeting_id=meeting_id,
                item_id=item_id,
                title=data.get("title") or "",
                description=data.get("description") or "",
                priority=data.get("priority") or "Normální",
                due_date=data.get("due_date"),
                remind_from=data.get("remind_from"),
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

        dialog = TaskDialog(self, create_factory=_create_for_item)
        dialog.exec()
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
        dialog.exec()
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

    def _on_current_row_changed(self, row: int) -> None:
        if self._suppress_selection:
            return
        new_index = row if row >= 0 else None
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
        self._update_list_item_text(self._current_index)

    def _on_status_edited(self, status: str) -> None:
        if self._suppress_selection or self._current_index is None:
            return
        self._set_item_status(self._current_index, status)

    def _set_item_status(self, index: int, status: str) -> None:
        if not (0 <= index < len(self._items)):
            return
        normalized = meeting_agenda_item_service.normalize_status(status)
        self._items[index]["status"] = normalized
        self._update_list_item_text(index)
        if index == self._current_index and self.status_combo.currentText() != normalized:
            self._suppress_selection = True
            self.status_combo.setCurrentText(normalized)
            self._suppress_selection = False

    def _update_list_item_text(self, index: int) -> None:
        if not (0 <= index < self.list_widget.count()):
            return
        list_item = self.list_widget.item(index)
        if list_item is None:
            return
        list_item.setText(_item_label(index, self._items[index]))
        list_item.setToolTip(
            meeting_agenda_item_service.normalize_status(self._items[index].get("status"))
        )

    def _show_status_context_menu(self, pos) -> None:
        index = self.list_widget.indexAt(pos).row()
        if index < 0:
            return
        self.list_widget.setCurrentRow(index)
        menu = QMenu(self)
        submenu = menu.addMenu(AGENDA_ITEM_STATUS_MENU_TITLE)
        group = QActionGroup(submenu)
        group.setExclusive(True)
        current = meeting_agenda_item_service.normalize_status(
            self._items[index].get("status")
        )
        for status in AGENDA_ITEM_STATUSES:
            action = QAction(
                f"{AGENDA_ITEM_STATUS_ICONS[status]} {status}",
                submenu,
            )
            action.setCheckable(True)
            action.setChecked(status == current)
            action.triggered.connect(
                lambda *_args, row=index, value=status: self._set_item_status(row, value)
            )
            group.addAction(action)
            submenu.addAction(action)
        menu.exec(self.list_widget.viewport().mapToGlobal(pos))

    def _selected_index(self) -> int | None:
        row = self.list_widget.currentRow()
        return row if row >= 0 else None

    def _flush_editor_to_item(self) -> None:
        if self._current_index is None:
            return
        if not (0 <= self._current_index < len(self._items)):
            return
        if self.editor_stack.currentWidget() is not self.editor_panel:
            return
        self._items[self._current_index].update(
            {
                "title": self.title_edit.text().strip(),
                "status": meeting_agenda_item_service.normalize_status(
                    self.status_combo.currentText()
                ),
                "moje_sdeleni": self.moje_sdeleni_edit.toPlainText(),
                "prubeh_jednani": self.prubeh_jednani_edit.toPlainText(),
                "zaver": self.zaver_edit.toPlainText(),
            }
        )
        self._update_list_item_text(self._current_index)

    def _load_editor_from_item(self) -> None:
        if self._current_index is None or not (
            0 <= self._current_index < len(self._items)
        ):
            self._show_none_selected()
            return

        item = self._items[self._current_index]
        self._suppress_selection = True
        status = meeting_agenda_item_service.normalize_status(item.get("status"))
        self.status_combo.setCurrentText(status)
        self.title_edit.setText(item.get("title") or "")
        self.moje_sdeleni_edit.setPlainText(item.get("moje_sdeleni") or "")
        self.prubeh_jednani_edit.setPlainText(item.get("prubeh_jednani") or "")
        self.zaver_edit.setPlainText(item.get("zaver") or "")
        self._suppress_selection = False
        self.editor_stack.setCurrentWidget(self.editor_panel)
        self._refresh_tasks()

    def _show_none_selected(self) -> None:
        self._suppress_selection = True
        self.status_combo.setCurrentText(DEFAULT_AGENDA_ITEM_STATUS)
        self.title_edit.clear()
        self.moje_sdeleni_edit.clear()
        self.prubeh_jednani_edit.clear()
        self.zaver_edit.clear()
        self._suppress_selection = False
        self.tasks_table.setRowCount(0)
        self._task_ids = []
        self._update_task_buttons()
        self.editor_stack.setCurrentWidget(self.editor_stack.widget(0))

    def _clear_editor(self) -> None:
        self._show_none_selected()

    def _refresh_list(self, *, select_row: int | None = None) -> None:
        # Alias for older tests calling _refresh_table.
        self._refresh_table(select_row=select_row)

    def _refresh_table(self, *, select_row: int | None = None) -> None:
        for index, item in enumerate(self._items):
            item["display_order"] = (index + 1) * 10
            item["status"] = meeting_agenda_item_service.normalize_status(
                item.get("status")
            )

        self._suppress_selection = True
        self.list_widget.clear()
        for index, item in enumerate(self._items):
            list_item = QListWidgetItem(_item_label(index, item))
            list_item.setToolTip(
                meeting_agenda_item_service.normalize_status(item.get("status"))
            )
            self.list_widget.addItem(list_item)

        count = len(self._items)
        self.count_label.setText(AGENDA_ITEMS_COUNT_TEMPLATE.format(count=count))
        has_items = count > 0
        self.empty_label.setVisible(not has_items)
        self.list_widget.setVisible(has_items)

        if select_row is None or not has_items:
            self.list_widget.clearSelection()
            self.list_widget.setCurrentRow(-1)
            self._current_index = None
            self._suppress_selection = False
            self._show_none_selected()
            return

        select_row = max(0, min(select_row, count - 1))
        self.list_widget.setCurrentRow(select_row)
        self._current_index = select_row
        self._suppress_selection = False
        self._load_editor_from_item()
