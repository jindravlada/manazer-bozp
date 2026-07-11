from datetime import date

from PySide6.QtCore import QDate, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QSizePolicy

from core.dashboard.widget_base import DashboardPanel
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

    def _apply_formats(self):
        today_format = QTextCharFormat()
        today_format.setBackground(QColor("#eef6ff"))
        self.setDateTextFormat(QDate.currentDate(), today_format)

    def set_task_dates(self, task_dates):
        self._task_dates = task_dates or {}
        self.updateCells()

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
        for task in task_service.get_all_tasks():
            status = task.computed_status
            if task.due_date and status not in ["Ukončeno", "Zrušeno"]:
                if task.due_date < today:
                    kind = "overdue"
                elif task.due_date == today:
                    kind = "today"
                else:
                    kind = "future"
                task_dates.setdefault(task.due_date, set()).add(kind)
            if status == "Splněno - čeká na kontrolu" and task.check_due_date:
                task_dates.setdefault(task.check_due_date, set()).add("waiting")
            if status == "Ukončeno" and (task.checked_date or task.completed_date):
                task_dates.setdefault(task.checked_date or task.completed_date, set()).add("done")
        self.calendar.set_task_dates(task_dates)
