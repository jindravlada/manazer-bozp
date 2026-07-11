"""Panel Vyžaduje pozornost – úkoly, plánované audity a prověrky."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from core.dashboard.attention_item import AttentionItem
from core.dashboard.attention_service import get_attention_items
from core.dashboard.widget_base import DashboardPanel

_EMPTY_TEXT = "Aktuálně není nic, co by vyžadovalo pozornost."

COL_TYPE = 0
COL_DUE = 1
COL_TITLE = 2
COL_PRIORITY = 3
COL_SOURCE = 4

_ROLE_ITEM = Qt.ItemDataRole.UserRole

# Kalendář / termíny: po termínu, blížící se, budoucí
_COLOR_OVERDUE = QColor("#d93025")
_COLOR_APPROACHING = QColor("#f0a000")
_COLOR_FUTURE = QColor("#1a73e8")
_APPROACHING_DAYS = 7


class UpcomingTasksWidget(DashboardPanel):
    """Historický název třídy; panel zobrazuje Vyžaduje pozornost."""

    def __init__(
        self,
        open_tasks_callback=None,
        open_task_callback=None,
        open_attention_callback=None,
    ):
        super().__init__("Vyžaduje pozornost")
        self.open_tasks_callback = open_tasks_callback
        self.open_task_callback = open_task_callback
        self.open_attention_callback = open_attention_callback

        self.empty_label = QLabel(_EMPTY_TEXT)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Typ", "Termín", "Název", "Priorita", "Zdroj"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(COL_TYPE, 80)
        self.table.setColumnWidth(COL_DUE, 90)
        self.table.setColumnWidth(COL_PRIORITY, 80)
        self.table.doubleClicked.connect(self._open_selected)
        self.table.itemSelectionChanged.connect(self._update_open_button)

        buttons = QWidget()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)

        self.open_button = QPushButton("Otevřít")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_selected)

        buttons_layout.addWidget(self.open_button)
        buttons_layout.addStretch(1)

        self.layout.addWidget(self.empty_label, 1)
        self.layout.addWidget(self.table, 1)
        self.layout.addWidget(buttons)

        self.refresh()

    def _due_color(self, due_date: date | None, today: date) -> QColor | None:
        if due_date is None:
            return None
        if due_date < today:
            return _COLOR_OVERDUE
        if due_date <= today + timedelta(days=_APPROACHING_DAYS):
            return _COLOR_APPROACHING
        return _COLOR_FUTURE

    def _update_open_button(self) -> None:
        self.open_button.setEnabled(self._selected_item() is not None)

    def _selected_item(self) -> AttentionItem | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), COL_TYPE)
        if item is None:
            return None
        payload = item.data(_ROLE_ITEM)
        return payload if isinstance(payload, AttentionItem) else None

    def _open_selected(self, *_args) -> None:
        item = self._selected_item()
        if item is None:
            return
        if self.open_attention_callback:
            self.open_attention_callback(item)
            return
        if item.item_type == "task" and self.open_task_callback:
            self.open_task_callback(item.entity_id)

    def refresh(self) -> None:
        items = get_attention_items()
        self.table.setRowCount(0)

        if not items:
            self.empty_label.setText(_EMPTY_TEXT)
            self.empty_label.show()
            self.table.hide()
            self.open_button.setEnabled(False)
            return

        self.empty_label.hide()
        self.table.show()
        today = date.today()
        self.table.setRowCount(len(items))

        for row, attention in enumerate(items):
            type_item = QTableWidgetItem(attention.type_label)
            type_item.setData(_ROLE_ITEM, attention)

            due_text = (
                "bez termínu"
                if attention.due_date is None
                else attention.due_date.strftime("%d.%m.%Y")
            )
            due_item = QTableWidgetItem(due_text)
            due_color = self._due_color(attention.due_date, today)
            if due_color is not None:
                due_item.setForeground(QBrush(due_color))

            title_item = QTableWidgetItem(attention.title)
            priority_item = QTableWidgetItem(attention.priority or "—")
            source_item = QTableWidgetItem(attention.source_label or "—")

            self.table.setItem(row, COL_TYPE, type_item)
            self.table.setItem(row, COL_DUE, due_item)
            self.table.setItem(row, COL_TITLE, title_item)
            self.table.setItem(row, COL_PRIORITY, priority_item)
            self.table.setItem(row, COL_SOURCE, source_item)

        self.table.resizeRowsToContents()
        self._update_open_button()
