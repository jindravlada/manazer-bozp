from datetime import date

from PySide6.QtCore import QDate, QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QSizePolicy, QTableView, QToolTip

from core.dashboard.attention_service import (
    audit_title,
    inspection_title,
)
from core.dashboard.widget_base import DashboardPanel
from moduly.audity.sluzby.audit_service import audit_service
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.ukoly.sluzby.task_service import task_service

# Kompaktní, ale čitelný kalendář – pevná šířka, aby neroztahoval Dashboard.
_CALENDAR_WIDTH = 480
_CALENDAR_HEIGHT = 300
_PANEL_HEIGHT = 360
_DAY_FONT_POINT_SIZE = 12
_DAY_NUMBER_HEIGHT = 18
_WEEK_ROW_MIN_HEIGHT = 38


class TaskCalendarWidget(QCalendarWidget):
    def __init__(self):
        super().__init__()
        self._task_dates = {}
        self._day_events: dict[date, list[str]] = {}
        self._tooltip_date: date | None = None
        self._view: QTableView | None = None
        self.setObjectName("TaskCalendarWidget")
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.setSelectedDate(QDate.currentDate())
        self.setFixedSize(_CALENDAR_WIDTH, _CALENDAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
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
        QToolTip.hideText()

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
                        QToolTip.hideText()
        return super().eventFilter(obj, event)

    def _date_at(self, pos: QPoint) -> date | None:
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

        first = QDate(self.yearShown(), self.monthShown(), 1)
        first_dow = int(self.firstDayOfWeek().value)
        start_col = (first.dayOfWeek() - first_dow) % 7
        day_offset = index.row() * 7 + index.column() - start_col
        qdate = first.addDays(day_offset)
        if not qdate.isValid():
            return None
        return date(qdate.year(), qdate.month(), qdate.day())

    def _update_day_tooltip(self, pos: QPoint) -> None:
        day = self._date_at(pos)
        if day == self._tooltip_date:
            return
        self._tooltip_date = day
        events = self._day_events.get(day) if day is not None else None
        if not events:
            QToolTip.hideText()
            return
        lines = [day.strftime("%d.%m.%Y")]
        lines.extend(f"• {label}" for label in events)
        view = self._view
        if view is None:
            return
        try:
            global_pos = view.viewport().mapToGlobal(pos)
            QToolTip.showText(global_pos, "\n".join(lines), view.viewport())
        except RuntimeError:
            self._view = None
            QToolTip.hideText()

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


class CalendarPlaceholderWidget(DashboardPanel):
    def __init__(self):
        super().__init__("Kalendář úkolů")

        self.calendar = TaskCalendarWidget()
        self.layout.addWidget(self.calendar, 0, Qt.AlignHCenter)
        self.setFixedHeight(_PANEL_HEIGHT)
        self.setMinimumHeight(_PANEL_HEIGHT)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.refresh()

    def refresh(self):
        today = date.today()
        task_dates = {}
        day_events: dict[date, list[str]] = {}

        for task in task_service.get_all_tasks():
            status = task.computed_status
            title = (task.title or "").strip() or f"Úkol #{task.id}"
            label = f"Úkol – {title}"
            if task.due_date and status not in ["Ukončeno", "Zrušeno"]:
                if task.due_date < today:
                    kind = "overdue"
                elif task.due_date == today:
                    kind = "today"
                else:
                    kind = "future"
                task_dates.setdefault(task.due_date, set()).add(kind)
                day_events.setdefault(task.due_date, []).append(label)
            if status == "Splněno - čeká na kontrolu" and task.check_due_date:
                task_dates.setdefault(task.check_due_date, set()).add("waiting")
                day_events.setdefault(task.check_due_date, []).append(label)
            if status == "Ukončeno" and (task.checked_date or task.completed_date):
                done_date = task.checked_date or task.completed_date
                task_dates.setdefault(done_date, set()).add("done")
                day_events.setdefault(done_date, []).append(label)

        for audit in audit_service.get_all():
            due = audit.started_at
            if due is None:
                continue
            day_events.setdefault(due, []).append(audit_title(audit))

        for inspection in bozp_inspection_service.get_all():
            due = inspection.started_at
            if due is None:
                continue
            day_events.setdefault(due, []).append(inspection_title(inspection))

        self.calendar.set_task_dates(task_dates)
        self.calendar.set_day_events(day_events)
