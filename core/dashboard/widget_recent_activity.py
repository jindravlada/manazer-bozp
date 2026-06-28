from PySide6.QtWidgets import QLabel

from core.dashboard.widget_base import DashboardPanel
from moduly.ukoly.sluzby.task_service import task_service


class RecentActivityWidget(DashboardPanel):
    def __init__(self):
        super().__init__("Poslední aktivita")
        self.content = QLabel()
        self.content.setWordWrap(True)
        self.layout.addWidget(self.content)
        self.refresh()

    def refresh(self):
        tasks = task_service.get_all_tasks()
        tasks.sort(key=lambda task: task.updated_at, reverse=True)

        lines = []
        for task in tasks[:6]:
            stamp = task.updated_at.strftime("%d.%m.%Y %H:%M") if task.updated_at else ""
            lines.append(f"<b>{stamp}</b><br>{task.title}<br><span style='color:#666;'>{task.computed_status}</span><br>")

        if not lines:
            lines.append("Zatím není žádná aktivita.")

        self.content.setText("<br>".join(lines))
