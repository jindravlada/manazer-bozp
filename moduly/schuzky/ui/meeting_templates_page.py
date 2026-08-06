"""Přehled šablon událostí."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.schuzky.constants import (
    TEMPLATE_ACTION_DELETE,
    TEMPLATE_ACTION_EDIT,
    TEMPLATE_ACTION_NEW,
    TEMPLATE_COL_ITEMS,
    TEMPLATE_COL_NAME,
    TEMPLATE_COL_PRIORITY,
    TEMPLATE_COL_TYPE,
    TEMPLATE_DELETE_CONFIRM,
    TEMPLATE_DELETE_TITLE,
    TEMPLATE_EMPTY_LIST,
    TEMPLATE_LIST_TITLE,
    TEMPLATE_NOT_FOUND,
)
from moduly.schuzky.sluzby.meeting_template_service import (
    MeetingTemplateValidationError,
    meeting_template_service,
)
from moduly.schuzky.ui.meeting_template_dialog import MeetingTemplateDialog


class MeetingTemplatesPage(QWidget):
    """preferred_template_id: int | None – šablona k výběru po změně (None = bez preference)."""

    templates_changed = Signal(object)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(TEMPLATE_ACTION_NEW)
        self.edit_btn = QPushButton(TEMPLATE_ACTION_EDIT)
        self.delete_btn = QPushButton(TEMPLATE_ACTION_DELETE)
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self._selection_action_buttons = (self.edit_btn, self.delete_btn)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addStretch()

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                TEMPLATE_COL_NAME,
                TEMPLATE_COL_TYPE,
                TEMPLATE_COL_PRIORITY,
                TEMPLATE_COL_ITEMS,
            ]
        )
        self.table.setColumnHidden(0, True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        configure_table_columns(self.table, "meeting_templates")

        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat šablonu...")
        self.empty_label = QLabel(TEMPLATE_EMPTY_LIST)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty_label)

        self.new_btn.clicked.connect(self.new_template)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.delete_btn.clicked.connect(self.delete_selected)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self._refresh_action_buttons()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        super().hideEvent(event)

    def refresh(self) -> None:
        templates = meeting_template_service.get_all()
        self.table.setRowCount(0)
        self.table.setRowCount(len(templates))
        for row, template in enumerate(templates):
            self.table.setItem(row, 0, QTableWidgetItem(str(template.id)))
            self.table.setItem(row, 1, QTableWidgetItem(template.name or ""))
            self.table.setItem(row, 2, QTableWidgetItem(template.event_type or ""))
            self.table.setItem(row, 3, QTableWidgetItem(template.priority or ""))
            count = meeting_template_service.agenda_item_count(template)
            self.table.setItem(row, 4, QTableWidgetItem(str(count)))
        has_rows = bool(templates)
        self.table.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)
        configure_table_columns(self.table, "meeting_templates")
        self.text_filter.update_count()
        self.table.clearSelection()
        self._refresh_action_buttons()

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
        edit_action = menu.addAction(TEMPLATE_ACTION_EDIT, self.edit_selected)
        edit_action.setEnabled(enabled)
        delete_action = menu.addAction(TEMPLATE_ACTION_DELETE, self.delete_selected)
        delete_action.setEnabled(enabled)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _selected_template_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None
        return int(item.text())

    def new_template(self) -> None:
        dialog = MeetingTemplateDialog(self)
        if not exec_maximized(dialog):
            return
        try:
            created = meeting_template_service.create_template(**dialog.get_data())
        except MeetingTemplateValidationError as error:
            QMessageBox.warning(self, TEMPLATE_LIST_TITLE, str(error))
            return
        self.refresh()
        self.templates_changed.emit(int(created.id))

    def edit_selected(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            return
        template = meeting_template_service.get_by_id(template_id)
        if template is None:
            QMessageBox.warning(self, TEMPLATE_LIST_TITLE, TEMPLATE_NOT_FOUND)
            self.refresh()
            self.templates_changed.emit(None)
            return

        dialog = MeetingTemplateDialog(self, template=template)
        if not exec_maximized(dialog):
            return
        try:
            meeting_template_service.update_template(template_id, **dialog.get_data())
        except MeetingTemplateValidationError as error:
            QMessageBox.warning(self, TEMPLATE_LIST_TITLE, str(error))
            return
        self.refresh()
        self.templates_changed.emit(template_id)

    def delete_selected(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            return
        answer = QMessageBox.question(
            self,
            TEMPLATE_DELETE_TITLE,
            TEMPLATE_DELETE_CONFIRM,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        meeting_template_service.delete_template(template_id)
        self.refresh()
        self.templates_changed.emit(None)
