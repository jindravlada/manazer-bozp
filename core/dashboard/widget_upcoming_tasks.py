from datetime import date

from PySide6.QtWidgets import QLabel, QPushButton

from core.dashboard.widget_base import DashboardPanel
from moduly.ukoly.sluzby.task_service import task_service


class UpcomingTasksWidget(DashboardPanel):
    def __init__(self, open_tasks_callback=None):
        super().__init__("Nejbližší úkoly")
        self.open_tasks_callback = open_tasks_callback

        self.content = QLabel()
        self.content.setWordWrap(True)

        self.open_button = QPushButton("Otevřít Úkoly")
        if self.open_tasks_callback:
            self.open_button.clicked.connect(self.open_tasks_callback)

        self.layout.addWidget(self.content)
        self.layout.addWidget(self.open_button)

        self.refresh()

    def refresh(self):
        tasks = [
            task for task in task_service.get_all_tasks()
            if task.computed_status not in ["Ukončeno", "Zrušeno"]
        ]

        tasks.sort(key=lambda task: (task.due_date or date.max, task.id))

        lines = []
        for task in tasks[:6]:
            term = "bez termínu" if task.due_date is None else task.due_date.strftime("%d.%m.%Y")
            place = task.workplace_name or "—"
            lines.append(f"<b>{term}</b><br>{task.title}<br><span style='color:#666;'>📍 {place}</span><br>")

        if not lines:
            lines.append("Nejsou evidovány žádné aktivní úkoly.")

        self.content.setText("<br>".join(lines))
