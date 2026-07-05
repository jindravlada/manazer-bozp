from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from core.dashboard.task_links import configure_task_label, task_id_from_link, task_link
from core.dashboard.widget_base import DashboardPanel
from moduly.ukoly.sluzby.task_service import task_service


class TodayWidget(DashboardPanel):
    def __init__(self, open_task_callback=None):
        super().__init__("Co hoří")
        self.open_task_callback = open_task_callback

        self.content = QLabel()
        configure_task_label(self.content)
        self.content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content.linkActivated.connect(self._on_task_link_clicked)

        self.layout.addWidget(self.content, 1)
        self.setFixedHeight(170)
        self.refresh()

    def _task_line(self, task, prefix):
        term = task.due_date.strftime("%d.%m.%Y") if task.due_date else "bez termínu"
        place = task.workplace_name or "—"
        title = task_link(task.id, task.title)
        return (
            f"{prefix} <b>{term}</b> – {title}"
            f"<br><span style='color:#666;'>📍 {place}</span>"
        )

    def _on_task_link_clicked(self, link: str) -> None:
        task_id = task_id_from_link(link)
        if task_id is not None and self.open_task_callback:
            self.open_task_callback(task_id)

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
        due_today.sort(key=lambda task: (task.due_date or date.max, task.id))
        waiting.sort(key=lambda task: (task.check_due_date or date.max, task.id))

        ordered = []
        ordered.extend((task, "🔴") for task in burning)
        ordered.extend((task, "🔵") for task in due_today)
        ordered.extend((task, "🟡") for task in waiting)

        lines = [self._task_line(task, prefix) for task, prefix in ordered[:5]]

        if not lines:
            lines.append("Dnes není nic kritického.")

        self.content.setText("<br>".join(lines))
