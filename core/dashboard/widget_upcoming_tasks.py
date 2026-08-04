"""Panel Nadcházející události a úkoly."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QWidget,
)

from core.dashboard.attention_item import (
    ITEM_TYPE_AUDIT,
    ITEM_TYPE_INSPECTION,
    ITEM_TYPE_MEETING,
    ITEM_TYPE_TASK,
    PRIORITY_RANK,
    AttentionItem,
)
from core.dashboard.attention_service import get_attention_items
from core.dashboard.widget_base import DashboardPanel
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_datetime,
    typed_empty,
    typed_status,
    typed_text,
)

_TYPE_STABLE_PREFIX = {
    ITEM_TYPE_TASK: 1,
    ITEM_TYPE_AUDIT: 2,
    ITEM_TYPE_INSPECTION: 3,
    ITEM_TYPE_MEETING: 4,
}

_EMPTY_TEXT = "Nejsou evidovány žádné nadcházející události ani úkoly."

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
    """Historický název třídy; panel zobrazuje nadcházející události a úkoly."""

    def __init__(
        self,
        open_tasks_callback=None,
        open_task_callback=None,
        open_attention_callback=None,
        open_schuzky_callback=None,
    ):
        super().__init__("Nadcházející události a úkoly")
        self.open_tasks_callback = open_tasks_callback
        self.open_task_callback = open_task_callback
        self.open_attention_callback = open_attention_callback
        self.open_schuzky_callback = open_schuzky_callback

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
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(COL_TYPE, 80)
        self.table.setColumnWidth(COL_DUE, 150)
        self.table.setColumnWidth(COL_PRIORITY, 80)
        self.table.setColumnWidth(COL_SOURCE, 120)
        self.table.doubleClicked.connect(self._open_selected)
        self.table.itemSelectionChanged.connect(self._update_open_button)
        enable_typed_sorting(self.table)
        # Výchozí řazení podle termínu (nejbližší / po termínu nahoře), ne podle Typu.
        self.table.horizontalHeader().setSortIndicator(
            COL_DUE,
            Qt.SortOrder.AscendingOrder,
        )

        buttons = QWidget()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)

        self.open_button = QPushButton("Otevřít")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_selected)

        self.meetings_button = QPushButton("Události")
        self.meetings_button.setToolTip("Evidence událostí")
        if self.open_schuzky_callback:
            self.meetings_button.clicked.connect(self.open_schuzky_callback)
        else:
            self.meetings_button.setEnabled(False)

        buttons_layout.addWidget(self.open_button)
        buttons_layout.addWidget(self.meetings_button)
        buttons_layout.addStretch(1)

        self.layout.addWidget(self.empty_label, 1)
        self.layout.addWidget(self.table, 1)
        self.layout.addWidget(buttons)

        self.refresh()

    def _is_overdue(self, attention: AttentionItem, now: datetime) -> bool:
        if attention.event_at is not None:
            return attention.event_at < now
        if attention.due_date is None:
            return False
        return attention.due_date < now.date()

    def _due_color(self, attention: AttentionItem, now: datetime) -> QColor | None:
        if attention.event_at is not None:
            if attention.event_at < now:
                return _COLOR_OVERDUE
            if attention.event_at.date() <= now.date() + timedelta(days=_APPROACHING_DAYS):
                return _COLOR_APPROACHING
            return _COLOR_FUTURE
        due_date = attention.due_date
        if due_date is None:
            return None
        today = now.date()
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
        now = datetime.now()

        with sorting_paused(self.table):
            self.table.setRowCount(len(items))

            for row, attention in enumerate(items):
                stable_id = (
                    _TYPE_STABLE_PREFIX.get(attention.item_type, 9) * 1_000_000_000
                    + int(attention.entity_id)
                )
                type_item = create_typed_item(
                    attention.type_label,
                    typed_text(attention.type_label),
                    stable_id=stable_id,
                )
                type_item.setData(_ROLE_ITEM, attention)

                due_text = self._format_due_text(attention, now)
                due_sort = (
                    typed_datetime(attention.event_at)
                    if attention.event_at is not None
                    else typed_date(attention.due_date)
                )
                due_item = create_typed_item(
                    due_text,
                    due_sort,
                    stable_id=stable_id,
                )
                due_color = self._due_color(attention, now)
                if due_color is not None:
                    due_item.setForeground(QBrush(due_color))

                title_item = create_typed_item(
                    attention.title,
                    typed_text(attention.title),
                    stable_id=stable_id,
                )

                priority_rank = PRIORITY_RANK.get(attention.priority) if attention.priority else None
                priority_sort = (
                    typed_status(priority_rank, label=attention.priority)
                    if priority_rank is not None
                    else typed_empty()
                )
                priority_item = create_typed_item(
                    attention.priority or "—",
                    priority_sort,
                    stable_id=stable_id,
                )

                source_item = create_typed_item(
                    attention.source_label or "—",
                    typed_text(attention.source_label),
                    stable_id=stable_id,
                )

                self.table.setItem(row, COL_TYPE, type_item)
                self.table.setItem(row, COL_DUE, due_item)
                self.table.setItem(row, COL_TITLE, title_item)
                self.table.setItem(row, COL_PRIORITY, priority_item)
                self.table.setItem(row, COL_SOURCE, source_item)

        self.table.resizeRowsToContents()
        self._update_open_button()

    def _format_due_text(self, attention: AttentionItem, now: datetime) -> str:
        if attention.event_at is not None:
            starts = attention.event_at
            text = (
                f"{starts.day}. {starts.month}. {starts.year} "
                f"{starts.hour}:{starts.minute:02d}"
            )
            if attention.ends_at is not None:
                ends = attention.ends_at
                text += f"–{ends.hour}:{ends.minute:02d}"
            if self._is_overdue(attention, now):
                return f"{text} (Po termínu)"
            return text

        due_date = attention.due_date
        if due_date is None:
            return "bez termínu"
        text = f"{due_date.day}. {due_date.month}. {due_date.year}"
        if self._is_overdue(attention, now):
            return f"{text} (Po termínu)"
        return text
