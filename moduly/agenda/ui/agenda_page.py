"""Společný přehled Agendy – úkoly a události."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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
    ACTION_NEW_MEETING,
    ACTION_NEW_TASK,
    ACTION_OPEN,
    EMPTY_STATE_TEXT,
    ITEM_NOT_FOUND_MESSAGE,
    ITEM_TYPE_MEETING,
    ITEM_TYPE_TASK,
    LIST_WINDOW_TITLE,
    MEETING_STATUS_FILTERS,
    SELECT_ITEM_MESSAGE,
    TASK_STATUS_FILTERS,
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
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog


class AgendaPage(QWidget):
    def __init__(self):
        super().__init__()
        self._dashboard_refresh_callback = None

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_task_btn = QPushButton(ACTION_NEW_TASK)
        self.new_meeting_btn = QPushButton(ACTION_NEW_MEETING)
        self.open_btn = QPushButton(ACTION_OPEN)
        self.edit_btn = QPushButton(ACTION_EDIT)
        toolbar.addWidget(self.new_task_btn)
        toolbar.addWidget(self.new_meeting_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addStretch()

        self.type_checks: dict[str, QCheckBox] = {
            ITEM_TYPE_TASK: QCheckBox(TYPE_FILTER_TASKS),
            ITEM_TYPE_MEETING: QCheckBox(TYPE_FILTER_MEETINGS),
        }
        for check in self.type_checks.values():
            check.setChecked(True)
            check.toggled.connect(self.refresh)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Typ:"))
        for check in self.type_checks.values():
            type_row.addWidget(check)
        type_row.addStretch()

        self.status_checks: dict[str, QCheckBox] = {}
        status_box = QGroupBox("Stav")
        status_layout = QVBoxLayout(status_box)

        task_row = QHBoxLayout()
        task_row.addWidget(QLabel("Úkoly:"))
        for label in TASK_STATUS_FILTERS:
            check = QCheckBox(label)
            check.setChecked(True)
            check.toggled.connect(self.refresh)
            self.status_checks[f"task:{label}"] = check
            task_row.addWidget(check)
        task_row.addStretch()
        status_layout.addLayout(task_row)

        meeting_row = QHBoxLayout()
        meeting_row.addWidget(QLabel("Události:"))
        for label in MEETING_STATUS_FILTERS:
            check = QCheckBox(label)
            check.setChecked(True)
            check.toggled.connect(self.refresh)
            self.status_checks[f"meeting:{label}"] = check
            meeting_row.addWidget(check)
        meeting_row.addStretch()
        status_layout.addLayout(meeting_row)

        self.table = AgendaTable()
        configure_table_columns(self.table, "agenda")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat v agendě...")
        self.empty_label = QLabel(EMPTY_STATE_TEXT)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        layout.addLayout(toolbar)
        layout.addLayout(type_row)
        layout.addWidget(status_box)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.table)

        self.new_task_btn.clicked.connect(self.new_task)
        self.new_meeting_btn.clicked.connect(self.new_meeting)
        self.open_btn.clicked.connect(self.open_selected)
        self.edit_btn.clicked.connect(self.open_selected)
        self.table.doubleClicked.connect(self.open_selected)

        self.refresh()

    def set_dashboard_refresh_callback(self, callback) -> None:
        self._dashboard_refresh_callback = callback

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

    def _selected_status_filters_for(self, item_type: str) -> set[str]:
        prefix = f"{item_type}:"
        return {
            key.split(":", 1)[1]
            for key, check in self.status_checks.items()
            if key.startswith(prefix) and check.isChecked()
        }

    def refresh(self) -> None:
        items = agenda_service.filter_items(
            agenda_service.get_items(),
            type_filters=self._selected_type_filters(),
            task_status_filters=self._selected_status_filters_for(ITEM_TYPE_TASK),
            meeting_status_filters=self._selected_status_filters_for(ITEM_TYPE_MEETING),
        )
        self.table.load_items(items)
        configure_table_columns(self.table, "agenda")
        self.table.clear_selection()
        self.text_filter.update_count()

        if items:
            self.empty_label.hide()
            self.table.show()
        else:
            self.empty_label.setText(EMPTY_STATE_TEXT)
            self.empty_label.show()
            self.table.hide()

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

    def open_selected(self) -> None:
        item = self.table.selected_item()
        if item is None:
            QMessageBox.information(self, LIST_WINDOW_TITLE, SELECT_ITEM_MESSAGE)
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
