from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from core.dashboard.widget_base import DashboardPanel
from moduly.ukoly.sluzby.task_service import task_service


class TodayWidget(DashboardPanel):
    def __init__(self):
        super().__init__("Co hoří")
        self.content = QLabel()
        self.content.setWordWrap(True)
        self.content.setTextFormat(Qt.RichText)
        self.content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.content)
        self.setFixedHeight(170)
        self.refresh()

    def _task_line(self, task, prefix):
        term = task.due_date.strftime("%d.%m.%Y") if task.due_date else "bez termínu"
        place = task.workplace_name or "—"
        return (
            f"{prefix} <b>{term}</b> – {task.title}"
            f"<br><span style='color:#666;'>📍 {place}</span>"
        )

    def refresh(self):
        tasks = task_service.get_all_tasks()
        today = date.today()

        burning = []
        waiting = []
        due_today = []

        for task in tasks:
            status = task.computed_status
            if task.due_date and task.due_date < today and status not in ["Ukončeno", "Zrušeno"]:
                burning.append(task)
            elif status == "Splněno - čeká na kontrolu":
                waiting.append(task)
            elif task.due_date == today and status not in ["Ukončeno", "Zrušeno"]:
                due_today.append(task)

        burning.sort(key=lambda task: (task.due_date or date.max, task.id))
        waiting.sort(key=lambda task: (task.check_due_date or date.max, task.id))
        due_today.sort(key=lambda task: (task.due_date or date.max, task.id))

        lines = []
        for task in burning[:4]:
            lines.append(self._task_line(task, "🔴"))
        for task in waiting[:3]:
            lines.append(self._task_line(task, "🟡"))
        for task in due_today[:3]:
            lines.append(self._task_line(task, "🔵"))

        if not lines:
            lines.append("Žádný úkol ani opatření po termínu.")

        self.content.setText("<br>".join(lines))
