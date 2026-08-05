"""Přehled šablon událostí."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.schuzky.constants import (
    TEMPLATE_ACTION_EDIT,
    TEMPLATE_ACTION_NEW,
    TEMPLATE_ACTION_OPEN,
    TEMPLATE_ACTION_REMOVE,
    TEMPLATE_COL_ITEMS,
    TEMPLATE_COL_NAME,
    TEMPLATE_COL_PRIORITY,
    TEMPLATE_COL_TYPE,
    TEMPLATE_EMPTY_LIST,
    TEMPLATE_LIST_TITLE,
    TEMPLATE_NOT_FOUND,
    TEMPLATE_REMOVE_CONFIRM,
    TEMPLATE_REMOVE_TITLE,
    TEMPLATE_SELECT_MESSAGE,
)
from moduly.schuzky.sluzby.meeting_template_service import (
    MeetingTemplateValidationError,
    meeting_template_service,
)
from moduly.schuzky.ui.meeting_template_dialog import MeetingTemplateDialog


class MeetingTemplatesPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(TEMPLATE_ACTION_NEW)
        self.open_btn = QPushButton(TEMPLATE_ACTION_OPEN)
        self.edit_btn = QPushButton(TEMPLATE_ACTION_EDIT)
        self.remove_btn = QPushButton(TEMPLATE_ACTION_REMOVE)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.remove_btn)
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
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
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
        self.open_btn.clicked.connect(self.open_selected)
        self.edit_btn.clicked.connect(self.open_selected)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.table.doubleClicked.connect(self.open_selected)

        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)

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

    def _selected_template_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
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
            meeting_template_service.create_template(**dialog.get_data())
        except MeetingTemplateValidationError as error:
            QMessageBox.warning(self, TEMPLATE_LIST_TITLE, str(error))
            return
        self.refresh()

    def open_selected(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            QMessageBox.information(self, TEMPLATE_LIST_TITLE, TEMPLATE_SELECT_MESSAGE)
            return
        template = meeting_template_service.get_by_id(template_id)
        if template is None:
            QMessageBox.warning(self, TEMPLATE_LIST_TITLE, TEMPLATE_NOT_FOUND)
            self.refresh()
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

    def remove_selected(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            QMessageBox.information(self, TEMPLATE_LIST_TITLE, TEMPLATE_SELECT_MESSAGE)
            return
        answer = QMessageBox.question(
            self,
            TEMPLATE_REMOVE_TITLE,
            TEMPLATE_REMOVE_CONFIRM,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        meeting_template_service.delete_template(template_id)
        self.refresh()
