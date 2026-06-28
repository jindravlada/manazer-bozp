from datetime import date

from PySide6.QtCore import QDate, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QSizePolicy

from core.dashboard.widget_base import DashboardPanel
from moduly.ukoly.sluzby.task_service import task_service


class TaskCalendarWidget(QCalendarWidget):
    def __init__(self):
        super().__init__()
        self._task_dates = {}
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.setSelectedDate(QDate.currentDate())
        self.setFixedSize(620, 245)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._apply_formats()

    def _apply_formats(self):
        today_format = QTextCharFormat()
        today_format.setBackground(QColor("#eef6ff"))
        self.setDateTextFormat(QDate.currentDate(), today_format)

    def set_task_dates(self, task_dates):
        self._task_dates = task_dates or {}
        self.updateCells()

    def paintCell(self, painter: QPainter, rect: QRect, qdate: QDate):
        super().paintCell(painter, rect, qdate)
        py_date = date(qdate.year(), qdate.month(), qdate.day())
        statuses = self._task_dates.get(py_date, set())
        if not statuses:
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

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        radius = 4
        spacing = 4
        total = len(colors) * radius * 2 + max(0, len(colors) - 1) * spacing
        x = rect.center().x() - total // 2
        y = rect.bottom() - 12
        for color in colors[:4]:
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(x, y, radius * 2, radius * 2)
            x += radius * 2 + spacing
        painter.restore()


class CalendarPlaceholderWidget(DashboardPanel):
    def __init__(self):
        super().__init__("Kalendář úkolů")

        self.calendar = TaskCalendarWidget()
        self.layout.addWidget(self.calendar, 0, Qt.AlignHCenter)
        self.layout.addStretch(1)
        self.setFixedHeight(310)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
