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
from moduly.schuzky.constants import LIST_WINDOW_TITLE
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.sluzby.meeting_service import (
    MeetingValidationError,
    meeting_service,
)
from moduly.schuzky.ui.meeting_dialog import MeetingDialog
from moduly.schuzky.ui.meeting_table import MeetingTable


class SchuzkyPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nová událost")
        self.open_btn = QPushButton("Otevřít")
        self.edit_btn = QPushButton("Upravit")

        toolbar.addWidget(self.new_btn)
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
        self.open_btn.clicked.connect(self.open_selected_meeting)
        self.edit_btn.clicked.connect(self.open_selected_meeting)
        self.table.doubleClicked.connect(self.open_selected_meeting)

        self.refresh()

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
        window = self.window()
        page_widgets = getattr(window, "_page_widgets", None)
        if not isinstance(page_widgets, dict):
            return
        dashboard = page_widgets.get("dashboard")
        if dashboard is not None and hasattr(dashboard, "refresh"):
            dashboard.refresh()
