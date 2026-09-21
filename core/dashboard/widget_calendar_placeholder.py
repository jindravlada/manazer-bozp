"""Kalendář úkolů a událostí na pracovní ploše."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QDate, QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QSizePolicy, QTableView, QToolTip

from core.widgets.persistent_tooltips import (
    TOOLTIP_DISPLAY_MS,
    hide_persistent_tooltip,
    show_persistent_tooltip,
)

from core.dashboard.widget_base import DashboardPanel
from moduly.agenda.constants import (
    ITEM_TYPE_MEETING,
    ITEM_TYPE_TASK,
    ROW_STATE_CANCELED,
    ROW_STATE_DONE,
    ROW_STATE_OVERDUE,
    ROW_STATE_WAITING,
    TYPE_LABEL_MEETING,
    TYPE_LABEL_TASK,
)
from moduly.agenda.sluzby.agenda_service import AgendaItem, agenda_service

# Kompaktní kalendář – preferred velikost, aby při užším okně neblokoval zmenšení.
_CALENDAR_WIDTH = 420
_CALENDAR_HEIGHT = 280
_PANEL_MIN_HEIGHT = 300
_DAY_FONT_POINT_SIZE = 12
_DAY_NUMBER_HEIGHT = 18
_WEEK_ROW_MIN_HEIGHT = 38

# Stejná výdrž jako globální tooltipy (UX-TASK-TOOLTIP-1).
_TOOLTIP_DURATION_MS = TOOLTIP_DISPLAY_MS

# Model QCalendarWidget při NoVerticalHeader:
# řádek 0 = názvy dnů, sloupce 0–6 = po–ne (bez sloupce čísla týdne).
_HEADER_ROW = 0


class TaskCalendarWidget(QCalendarWidget):
    def __init__(self):
        super().__init__()
        self._task_dates: dict[date, set[str]] = {}
        self._day_events: dict[date, list[str]] = {}
        self._tooltip_date: date | None = None
        self._view: QTableView | None = None
        self.setObjectName("TaskCalendarWidget")
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.setSelectedDate(QDate.currentDate())
        self.resize(_CALENDAR_WIDTH, _CALENDAR_HEIGHT)
        self.setMinimumSize(280, 220)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setStyleSheet(f"""
            QCalendarWidget#TaskCalendarWidget {{
                background-color: #ffffff;
                border: none;
            }}
            QCalendarWidget#TaskCalendarWidget QWidget#qt_calendar_navigationbar {{
                min-height: 32px;
                max-height: 32px;
            }}
            QCalendarWidget#TaskCalendarWidget QHeaderView::section {{
                padding: 2px 0px;
                border: none;
                background-color: #ffffff;
                color: #6b7280;
                font-size: 12px;
            }}
            QCalendarWidget#TaskCalendarWidget QTableView {{
                gridline-color: transparent;
                border: none;
                background-color: #ffffff;
                alternate-background-color: #ffffff;
                outline: 0;
            }}
            QCalendarWidget#TaskCalendarWidget QTableView::item {{
                border: none;
                padding: 1px 0px;
                min-height: {_WEEK_ROW_MIN_HEIGHT}px;
            }}
            QCalendarWidget#TaskCalendarWidget QAbstractItemView:enabled {{
                selection-background-color: transparent;
                selection-color: #111827;
                font-size: {_DAY_FONT_POINT_SIZE}px;
            }}
        """)
        self._apply_formats()
        self._ensure_tooltip_hook()

    def _apply_formats(self):
        today_format = QTextCharFormat()
        today_format.setBackground(QColor("#eef6ff"))
        self.setDateTextFormat(QDate.currentDate(), today_format)

    def set_task_dates(self, task_dates):
        self._task_dates = task_dates or {}
        self.updateCells()

    def set_day_events(self, day_events: dict[date, list[str]] | None) -> None:
        self._day_events = day_events or {}
        self._tooltip_date = None
        hide_persistent_tooltip()

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_tooltip_hook()

    def _ensure_tooltip_hook(self) -> None:
        if self._view is not None:
            try:
                self._view.viewport()
                return
            except RuntimeError:
                self._view = None
        view = self.findChild(QTableView)
        if view is None:
            return
        self._view = view
        view.setMouseTracking(True)
        view.viewport().setMouseTracking(True)
        view.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        view = self._view
        if view is not None:
            try:
                viewport = view.viewport()
            except RuntimeError:
                self._view = None
            else:
                etype = event.type()
                if obj is viewport:
                    if etype == QEvent.Type.MouseMove:
                        pos = event.position().toPoint()
                        self._update_day_tooltip(pos)
                    elif etype == QEvent.Type.Leave:
                        self._tooltip_date = None
                        hide_persistent_tooltip()
        return super().eventFilter(obj, event)

    def _date_at(self, pos: QPoint) -> date | None:
        """Mapuje pozici kurzoru na den – počítá s řádkem názvů dnů."""
        view = self._view
        if view is None:
            return None
        try:
            index = view.indexAt(pos)
        except RuntimeError:
            self._view = None
            return None
        if not index.isValid():
            return None
        if index.row() <= _HEADER_ROW:
            return None

        first = QDate(self.yearShown(), self.monthShown(), 1)
        first_dow = int(self.firstDayOfWeek().value)
        start_col = (first.dayOfWeek() - first_dow) % 7
        week_row = index.row() - _HEADER_ROW - 1
        week_col = index.column()
        # Při zapnutém sloupci čísla týdne (8 sloupců) přeskočit první sloupec.
        try:
            if view.model() is not None and view.model().columnCount() >= 8:
                if week_col <= 0:
                    return None
                week_col -= 1
        except RuntimeError:
            self._view = None
            return None
        day_offset = week_row * 7 + week_col - start_col
        qdate = first.addDays(day_offset)
        if not qdate.isValid():
            return None
        return date(qdate.year(), qdate.month(), qdate.day())

    def _update_day_tooltip(self, pos: QPoint) -> None:
        day = self._date_at(pos)
        # Stejný den + stále viditelný tooltip → nic neměnit (pohyb uvnitř buňky).
        if day is not None and day == self._tooltip_date and QToolTip.isVisible():
            return
        self._tooltip_date = day
        events = self._day_events.get(day, []) if day is not None else []
        if not events:
            hide_persistent_tooltip()
            return
        # Text tooltipu vždy z aktuálních dat daného dne (žádná stará cache textu).
        text = "\n".join([day.strftime("%d.%m.%Y"), ""] + events)
        view = self._view
        if view is None:
            return
        try:
            viewport = view.viewport()
            index = view.indexAt(pos)
            cell_rect = view.visualRect(index) if index.isValid() else QRect()
            global_pos = viewport.mapToGlobal(pos)
            show_persistent_tooltip(global_pos, text, viewport, cell_rect)
        except RuntimeError:
            self._view = None
            hide_persistent_tooltip()

    def paintCell(self, painter: QPainter, rect: QRect, qdate: QDate):
        inset_y = 2
        cell = QRect(
            rect.left(),
            rect.top() + inset_y,
            rect.width(),
            max(1, rect.height() - inset_y * 2),
        )

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        fmt = self.dateTextFormat(qdate)
        if fmt.background().style() != Qt.BrushStyle.NoBrush:
            painter.fillRect(cell, fmt.background().color())

        is_outside = (
            qdate.month() != self.monthShown()
            or qdate.year() != self.yearShown()
        )
        font = painter.font()
        font.setPointSize(_DAY_FONT_POINT_SIZE)
        font.setBold(qdate == QDate.currentDate())
        painter.setFont(font)

        if fmt.foreground().style() != Qt.BrushStyle.NoBrush:
            painter.setPen(fmt.foreground().color())
        elif is_outside:
            painter.setPen(QColor("#cbd5e1"))
        else:
            painter.setPen(QColor("#374151"))

        day_rect = QRect(cell.left(), cell.top() + 2, cell.width(), _DAY_NUMBER_HEIGHT)
        painter.drawText(
            day_rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            str(qdate.day()),
        )

        py_date = date(qdate.year(), qdate.month(), qdate.day())
        statuses = self._task_dates.get(py_date, set())
        if not statuses:
            painter.restore()
            return

        colors = []
        if "overdue" in statuses:
            colors.append(QColor("#d93025"))
        if "waiting" in statuses:
            colors.append(QColor("#f0a000"))
        if "today" in statuses or "future" in statuses:
            colors.append(QColor("#1a73e8"))
        if "done" in statuses:
            colors.append(QColor("#1f8f3a"))

        radius = 4
        spacing = 4
        total = len(colors) * radius * 2 + max(0, len(colors) - 1) * spacing
        x = cell.center().x() - total // 2
        y = day_rect.bottom() + 3
        y = min(y, cell.bottom() - radius * 2 - 1)
        for color in colors[:4]:
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(x, y, radius * 2, radius * 2)
            x += radius * 2 + spacing
        painter.restore()


def _dot_kind(item: AgendaItem, *, today: date) -> str | None:
    if item.row_state == ROW_STATE_CANCELED:
        return None
    if item.row_state == ROW_STATE_DONE:
        return "done"
    if item.row_state == ROW_STATE_WAITING:
        return "waiting"
    if item.row_state == ROW_STATE_OVERDUE:
        return "overdue"
    day = item.due_date
    if day is None:
        return None
    if day < today:
        return "overdue"
    if day == today:
        return "today"
    return "future"


def _format_time_range(starts: datetime | None, ends: datetime | None) -> str:
    if starts is None:
        return ""
    text = f"{starts.hour:02d}:{starts.minute:02d}"
    if ends is not None:
        text += f"–{ends.hour:02d}:{ends.minute:02d}"
    return text


def _tooltip_block(item: AgendaItem) -> str:
    type_label = item.type_label or (
        TYPE_LABEL_MEETING if item.item_type == ITEM_TYPE_MEETING else TYPE_LABEL_TASK
    )
    title = item.tooltip_title
    if item.item_type == ITEM_TYPE_MEETING and item.event_at is not None:
        time_line = _format_time_range(item.event_at, item.ends_at)
        return f"• {time_line}\n  {type_label}\n  {title}"
    return f"• {type_label}\n  {title}"


def build_calendar_day_data(
    *,
    today: date | None = None,
    now: datetime | None = None,
) -> tuple[dict[date, set[str]], dict[date, list[str]]]:
    """Sestaví tečky a tooltipy z collectorů Agendy (úkoly + události)."""
    now = now or datetime.now()
    today = today or now.date()
    items = [
        item
        for item in agenda_service.get_items(today=today, now=now)
        if item.due_date is not None
        and item.row_state != ROW_STATE_CANCELED
        # Ukončené úkoly patří do filtrů Agendy, ne do kalendáře na ploše.
        and not (item.item_type == ITEM_TYPE_TASK and item.row_state == ROW_STATE_DONE)
    ]

    by_day: dict[date, list[AgendaItem]] = {}
    for item in items:
        by_day.setdefault(item.due_date, []).append(item)

    task_dates: dict[date, set[str]] = {}
    day_events: dict[date, list[str]] = {}
    for day, day_items in by_day.items():
        day_items.sort(key=lambda item: item.sort_key)
        kinds: set[str] = set()
        blocks: list[str] = []
        for item in day_items:
            kind = _dot_kind(item, today=today)
            if kind is not None:
                kinds.add(kind)
            blocks.append(_tooltip_block(item))
        if kinds:
            task_dates[day] = kinds
        if blocks:
            day_events[day] = blocks
    return task_dates, day_events


class CalendarPlaceholderWidget(DashboardPanel):
    def __init__(self):
        super().__init__("Kalendář")

        self.calendar = TaskCalendarWidget()
        self.layout.addWidget(self.calendar, 0, Qt.AlignHCenter)
        self.setMinimumHeight(_PANEL_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.refresh()

    def refresh(self):
        task_dates, day_events = build_calendar_day_data()
        self.calendar.set_task_dates(task_dates)
        self.calendar.set_day_events(day_events)
