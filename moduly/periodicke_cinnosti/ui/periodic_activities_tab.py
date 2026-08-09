"""Záložka Agendy – Periodické činnosti."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
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
from moduly.periodicke_cinnosti.constants import (
    ACTION_EDIT,
    ACTION_NEW,
    ACTION_PERFORM,
    EMPTY_STATE_TEXT,
    ITEM_NOT_FOUND_MESSAGE,
    SHOW_INACTIVE_LABEL,
    TAB_PERIODIC,
)
from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
    periodic_activity_service,
)
from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import PeriodicActivityDialog
from moduly.periodicke_cinnosti.ui.periodic_activity_table import PeriodicActivityTable
from moduly.periodicke_cinnosti.ui.periodic_performance_dialog import (
    PeriodicPerformanceDialog,
)


class PeriodicActivitiesTab(QWidget):
    def __init__(self, parent=None, *, on_changed=None):
        super().__init__(parent)
        self._on_changed = on_changed

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(ACTION_NEW)
        self.edit_btn = QPushButton(ACTION_EDIT)
        self.perform_btn = QPushButton(ACTION_PERFORM)
        self.edit_btn.setEnabled(False)
        self.perform_btn.setEnabled(False)
        self._selection_action_buttons = (self.edit_btn, self.perform_btn)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.perform_btn)
        toolbar.addStretch()
        self.show_inactive = QCheckBox(SHOW_INACTIVE_LABEL)
        toolbar.addWidget(self.show_inactive)

        self.table = PeriodicActivityTable()
        configure_table_columns(self.table, "periodic_activities")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat v periodických činnostech...")
        self.empty_label = QLabel(EMPTY_STATE_TEXT)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_activity)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.perform_btn.clicked.connect(self.perform_selected)
        self.show_inactive.toggled.connect(self.refresh)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def refresh(self) -> None:
        if self.show_inactive.isChecked():
            activities = periodic_activity_service.get_all()
        else:
            activities = periodic_activity_service.get_all(active_only=True)
        self.table.load_activities(activities)
        configure_table_columns(self.table, "periodic_activities")
        self.table.clear_selection()
        self.text_filter.update_count()
        self._refresh_action_buttons()

        if activities:
            self.empty_label.hide()
            self.table.show()
        else:
            self.empty_label.setText(EMPTY_STATE_TEXT)
            self.empty_label.show()
            self.table.hide()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _selected_activity(self):
        activity_id = self.table.selected_activity_id()
        if activity_id is None:
            return None
        return periodic_activity_service.get_by_id(activity_id)

    def _refresh_action_buttons(self, *_args) -> None:
        single = self._selected_row_count() == 1
        self.edit_btn.setEnabled(single)
        activity = self._selected_activity() if single else None
        self.perform_btn.setEnabled(bool(activity and activity.active))

    def _show_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()
        single = self._selected_row_count() == 1
        if not single and not index.isValid():
            return
        menu = QMenu(self)
        edit_action = menu.addAction(ACTION_EDIT, self.edit_selected)
        edit_action.setEnabled(self.edit_btn.isEnabled())
        perform_action = menu.addAction(ACTION_PERFORM, self.perform_selected)
        perform_action.setEnabled(self.perform_btn.isEnabled())
        menu.exec(self.table.viewport().mapToGlobal(position))

    def new_activity(self) -> None:
        dialog = PeriodicActivityDialog(self)
        exec_maximized(dialog)
        self.refresh()
        if dialog.activity is not None:
            self._notify_changed()

    def edit_selected(self) -> None:
        if self._selected_row_count() != 1:
            return
        activity = self._selected_activity()
        if activity is None:
            QMessageBox.warning(self, TAB_PERIODIC, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        dialog = PeriodicActivityDialog(self, activity=activity)
        exec_maximized(dialog)
        self.refresh()
        self._notify_changed()

    def open_activity(self, activity_id: int) -> None:
        activity = periodic_activity_service.get_by_id(activity_id)
        if activity is None:
            QMessageBox.warning(self, TAB_PERIODIC, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        if not activity.active:
            self.show_inactive.setChecked(True)
        self.refresh()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == activity_id:
                self.table.selectRow(row)
                break
        self._refresh_action_buttons()
        dialog = PeriodicActivityDialog(self, activity=activity)
        exec_maximized(dialog)
        self.refresh()
        self._notify_changed()

    def perform_selected(self) -> None:
        if not self.perform_btn.isEnabled():
            return
        activity = self._selected_activity()
        if activity is None:
            QMessageBox.warning(self, TAB_PERIODIC, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        dialog = PeriodicPerformanceDialog(
            self,
            activity_id=activity.id,
            activity_title=activity.title,
        )
        exec_maximized(dialog)
        self.refresh()
        if dialog.occurrence is not None:
            self._notify_changed()

    def _notify_changed(self) -> None:
        if callable(self._on_changed):
            self._on_changed()
