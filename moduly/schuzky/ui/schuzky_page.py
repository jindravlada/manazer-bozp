"""Přehled událostí."""

from __future__ import annotations

from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.schuzky.constants import (
    ACTION_NEW_FROM_TEMPLATE,
    ACTION_OPEN_TEMPLATES,
    LIST_WINDOW_TITLE,
)
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.sluzby.meeting_service import (
    MeetingValidationError,
    meeting_service,
)
from moduly.schuzky.ui.meeting_dialog import MeetingDialog
from moduly.schuzky.ui.meeting_table import MeetingTable
from moduly.schuzky.ui.meeting_template_actions import create_meeting_from_template


class SchuzkyPage(QWidget):
    def __init__(self):
        super().__init__()
        self._dashboard_refresh_callback = None

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nová událost")
        self.new_from_template_btn = QPushButton(ACTION_NEW_FROM_TEMPLATE)
        self.templates_btn = QPushButton(ACTION_OPEN_TEMPLATES)
        self.open_btn = QPushButton("Otevřít")
        self.edit_btn = QPushButton("Upravit")

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.new_from_template_btn)
        toolbar.addWidget(self.templates_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addStretch()

        self.table = MeetingTable()
        configure_table_columns(self.table, "meetings")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat událost...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_meeting)
        self.new_from_template_btn.clicked.connect(self.new_meeting_from_template)
        self.templates_btn.clicked.connect(self.open_templates)
        self.open_btn.clicked.connect(self.open_selected_meeting)
        self.edit_btn.clicked.connect(self.open_selected_meeting)
        self.table.doubleClicked.connect(self.open_selected_meeting)

        self.refresh()

    def set_dashboard_refresh_callback(self, callback) -> None:
        self._dashboard_refresh_callback = callback

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.table.clear_selection()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def refresh(self) -> None:
        meetings = meeting_service.get_all()
        self.table.load_meetings(meetings)
        configure_table_columns(self.table, "meetings")
        self.table.clear_selection()
        self.text_filter.update_count()

    def _selected_meeting_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None
        return int(item.text())

    def new_meeting(self) -> None:
        dialog = MeetingDialog(self)
        if not exec_maximized(dialog):
            return
        try:
            meeting = meeting_service.create_meeting(**dialog.get_data())
            meeting_agenda_item_service.save_items(meeting.id, dialog.get_agenda_items())
        except MeetingValidationError as error:
            QMessageBox.warning(self, LIST_WINDOW_TITLE, str(error))
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

    def open_selected_meeting(self) -> None:
        meeting_id = self._selected_meeting_id()
        if meeting_id is None:
            QMessageBox.information(self, LIST_WINDOW_TITLE, "Vyberte událost.")
            return
        self.open_meeting(meeting_id)

    def open_meeting(self, meeting_id: int) -> None:
        meeting = meeting_service.get_by_id(meeting_id)
        if meeting is None:
            QMessageBox.warning(self, LIST_WINDOW_TITLE, "Událost nebyla nalezena.")
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
            QMessageBox.warning(self, LIST_WINDOW_TITLE, str(error))
            return
        self.refresh()
        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        if callable(self._dashboard_refresh_callback):
            self._dashboard_refresh_callback()
            return

        widget = self
        while widget is not None:
            page_widgets = getattr(widget, "_page_widgets", None)
            if isinstance(page_widgets, dict):
                dashboard = page_widgets.get("dashboard")
                if dashboard is not None and hasattr(dashboard, "refresh"):
                    dashboard.refresh()
                return
            widget = widget.parent()
