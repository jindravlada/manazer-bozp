"""Společný přehled Agendy – úkoly a události."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.agenda.constants import (
    ACTION_EDIT,
    ACTION_NEW_FROM_TEMPLATE,
    ACTION_NEW_MEETING,
    ACTION_NEW_TASK,
    ACTION_OPEN_TEMPLATES,
    DEFAULT_STATUS_MODE,
    EMPTY_STATE_TEXT,
    ITEM_NOT_FOUND_MESSAGE,
    ITEM_TYPE_MEETING,
    ITEM_TYPE_TASK,
    LIST_WINDOW_TITLE,
    ROW_LEGEND,
    STATUS_MODE_ACTIVE,
    STATUS_MODES_BOTH,
    STATUS_MODES_MEETINGS_ONLY,
    STATUS_MODES_TASKS_ONLY,
    TYPE_FILTER_MEETINGS,
    TYPE_FILTER_TASKS,
)
from moduly.agenda.sluzby.agenda_service import agenda_service
from moduly.agenda.ui.agenda_table import AgendaTable
from moduly.schuzky.constants import LIST_WINDOW_TITLE as MEETINGS_TITLE
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.sluzby.meeting_service import (
    MeetingValidationError,
    meeting_service,
)
from moduly.schuzky.ui.meeting_dialog import MeetingDialog
from moduly.schuzky.ui.meeting_template_actions import create_meeting_from_template
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog


class AgendaPage(QWidget):
    def __init__(self):
        super().__init__()
        self._dashboard_refresh_callback = None
        self._updating_status_filter = False

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_task_btn = QPushButton(ACTION_NEW_TASK)
        self.new_meeting_btn = QPushButton(ACTION_NEW_MEETING)
        self.new_from_template_btn = QPushButton(ACTION_NEW_FROM_TEMPLATE)
        self.templates_btn = QPushButton(ACTION_OPEN_TEMPLATES)
        self.edit_btn = QPushButton(ACTION_EDIT)
        self.edit_btn.setEnabled(False)

        self._selection_action_buttons = (self.edit_btn,)

        toolbar.addWidget(self.new_task_btn)
        toolbar.addWidget(self.new_meeting_btn)
        toolbar.addWidget(self.new_from_template_btn)
        toolbar.addWidget(self.templates_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addStretch()

        self.type_checks: dict[str, QCheckBox] = {
            ITEM_TYPE_TASK: QCheckBox(TYPE_FILTER_TASKS),
            ITEM_TYPE_MEETING: QCheckBox(TYPE_FILTER_MEETINGS),
        }
        for check in self.type_checks.values():
            check.setChecked(True)
            check.toggled.connect(self._on_type_filter_changed)

        toolbar.addWidget(QLabel("Typ:"))
        for check in self.type_checks.values():
            toolbar.addWidget(check)

        toolbar.addWidget(QLabel("Zobrazit:"))
        self.status_filter = QComboBox()
        self.status_filter.currentIndexChanged.connect(self._on_status_filter_changed)
        toolbar.addWidget(self.status_filter)

        self.table = AgendaTable()
        configure_table_columns(self.table, "agenda")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat v agendě...")
        self.legend = QLabel(ROW_LEGEND)
        self.empty_label = QLabel(EMPTY_STATE_TEXT)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.legend)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.table)

        self.new_task_btn.clicked.connect(self.new_task)
        self.new_meeting_btn.clicked.connect(self.new_meeting)
        self.new_from_template_btn.clicked.connect(self.new_meeting_from_template)
        self.templates_btn.clicked.connect(self.open_templates)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self._rebuild_status_filter(preferred=DEFAULT_STATUS_MODE)
        self.refresh()

    def set_dashboard_refresh_callback(self, callback) -> None:
        self._dashboard_refresh_callback = callback

    def apply_workspace_filters(self) -> None:
        """Výchozí filtr z pracovní plochy: oba typy + Aktivní."""
        for check in self.type_checks.values():
            check.blockSignals(True)
            check.setChecked(True)
            check.blockSignals(False)
        self._rebuild_status_filter(preferred=STATUS_MODE_ACTIVE)
        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def _selected_type_filters(self) -> set[str]:
        return {
            key
            for key, check in self.type_checks.items()
            if check.isChecked()
        }

    def _status_modes_for_types(self, type_filters: set[str]) -> tuple[str, ...]:
        has_tasks = ITEM_TYPE_TASK in type_filters
        has_meetings = ITEM_TYPE_MEETING in type_filters
        if has_tasks and has_meetings:
            return STATUS_MODES_BOTH
        if has_tasks:
            return STATUS_MODES_TASKS_ONLY
        if has_meetings:
            return STATUS_MODES_MEETINGS_ONLY
        return STATUS_MODES_BOTH

    def _rebuild_status_filter(self, preferred: str | None = None) -> None:
        type_filters = self._selected_type_filters()
        modes = self._status_modes_for_types(type_filters)
        current = preferred or self.status_filter.currentText()
        if current not in modes:
            current = DEFAULT_STATUS_MODE if DEFAULT_STATUS_MODE in modes else modes[0]

        self._updating_status_filter = True
        self.status_filter.blockSignals(True)
        self.status_filter.clear()
        self.status_filter.addItems(list(modes))
        self.status_filter.setCurrentText(current)
        self.status_filter.blockSignals(False)
        self._updating_status_filter = False

    def _on_type_filter_changed(self) -> None:
        self._rebuild_status_filter()
        self.refresh()

    def _on_status_filter_changed(self) -> None:
        if self._updating_status_filter:
            return
        self.refresh()

    def refresh(self) -> None:
        items = agenda_service.filter_items(
            agenda_service.get_items(),
            type_filters=self._selected_type_filters(),
            status_mode=self.status_filter.currentText() or DEFAULT_STATUS_MODE,
        )
        self.table.load_items(items)
        configure_table_columns(self.table, "agenda")
        self.table.clear_selection()
        self.text_filter.update_count()
        self._refresh_action_buttons()

        if items:
            self.empty_label.hide()
            self.table.show()
        else:
            self.empty_label.setText(EMPTY_STATE_TEXT)
            self.empty_label.show()
            self.table.hide()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _refresh_action_buttons(self, *_args) -> None:
        enabled = self._selected_row_count() == 1
        for button in self._selection_action_buttons:
            button.setEnabled(enabled)

    def _show_table_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()

        enabled = self._selected_row_count() == 1
        if not enabled and not index.isValid():
            return

        menu = QMenu(self)
        edit_action = menu.addAction(ACTION_EDIT, self.edit_selected)
        edit_action.setEnabled(enabled)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def new_task(self) -> None:
        dialog = TaskDialog(self)
        if not dialog.exec():
            return
        data = dialog.get_data()
        if data["title"]:
            task_service.create_task(**data)
            self.refresh()
            self._refresh_dashboard()

    def new_meeting(self) -> None:
        dialog = MeetingDialog(self)
        if not exec_maximized(dialog):
            return
        try:
            meeting = meeting_service.create_meeting(**dialog.get_data())
            meeting_agenda_item_service.save_items(meeting.id, dialog.get_agenda_items())
        except MeetingValidationError as error:
            QMessageBox.warning(self, MEETINGS_TITLE, str(error))
            return
        self.refresh()
        self._refresh_dashboard()

    def new_meeting_from_template(self) -> None:
        if create_meeting_from_template(self):
            self.refresh()
            self._refresh_dashboard()

    def open_templates(self) -> None:
        widget = self
        while widget is not None:
            show = getattr(widget, "_show", None)
            if callable(show):
                show("sablony_udalosti")
                return
            widget = widget.parent()

    def edit_selected(self) -> None:
        if self._selected_row_count() != 1:
            return
        item = self.table.selected_item()
        if item is None:
            return
        if item.item_type == ITEM_TYPE_TASK:
            self._open_task(item.source_id)
        elif item.item_type == ITEM_TYPE_MEETING:
            self._open_meeting(item.source_id)

    def _open_task(self, task_id: int) -> None:
        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, LIST_WINDOW_TITLE, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        dialog = TaskDialog(self, task=task)
        if not dialog.exec():
            return
        data = dialog.get_data()
        if data["title"]:
            task_service.update_task(task_id=task_id, **data)
            self.refresh()
            self._refresh_dashboard()

    def _open_meeting(self, meeting_id: int) -> None:
        meeting = meeting_service.get_by_id(meeting_id)
        if meeting is None:
            QMessageBox.warning(self, LIST_WINDOW_TITLE, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            self._refresh_dashboard()
            return
        dialog = MeetingDialog(self, meeting=meeting)
        if not exec_maximized(dialog):
            return
        try:
            meeting_service.update_meeting(meeting_id, **dialog.get_data())
            meeting_agenda_item_service.save_items(meeting_id, dialog.get_agenda_items())
        except MeetingValidationError as error:
            QMessageBox.warning(self, MEETINGS_TITLE, str(error))
            return
        self.refresh()
        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        if callable(self._dashboard_refresh_callback):
            self._dashboard_refresh_callback()
