from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy

from core.dashboard.task_links import configure_task_label, task_id_from_link, task_link
from core.dashboard.widget_base import DashboardPanel
from moduly.ukoly.sluzby.task_service import task_service


class UpcomingTasksWidget(DashboardPanel):
    def __init__(self, open_tasks_callback=None, open_task_callback=None):
        super().__init__("Nejbližší úkoly")
        self.open_tasks_callback = open_tasks_callback
        self.open_task_callback = open_task_callback

        self.content = QLabel()
        configure_task_label(self.content)
        self.content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content.linkActivated.connect(self._on_task_link_clicked)

        self.open_button = QPushButton("Otevřít Úkoly")
        if self.open_tasks_callback:
            self.open_button.clicked.connect(self.open_tasks_callback)

        self.layout.addWidget(self.content, 1)
        self.layout.addWidget(self.open_button)

        self.refresh()

    def _on_task_link_clicked(self, link: str) -> None:
        task_id = task_id_from_link(link)
        if task_id is not None and self.open_task_callback:
            self.open_task_callback(task_id)

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
            title = task_link(task.id, task.title)
            lines.append(
                f"<b>{term}</b><br>{title}<br>"
                f"<span style='color:#666;'>📍 {place}</span><br>"
            )

        if not lines:
            lines.append("Nejsou evidovány žádné aktivní úkoly.")

        self.content.setText("<br>".join(lines))
