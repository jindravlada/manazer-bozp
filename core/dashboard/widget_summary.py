from datetime import date

from PySide6.QtWidgets import QHBoxLayout, QWidget

from core.dashboard.widget_base import DashboardCard
from moduly.ukoly.sluzby.task_service import task_service


class SummaryWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.overdue = DashboardCard("🔴 Po termínu", "0", "kritické věci k řešení")
        self.waiting = DashboardCard("🟡 Čeká kontrola", "0", "splněno, čeká na ověření")
        self.today = DashboardCard("🔵 Dnes", "0", "termín splnění dnes")
        self.done = DashboardCard("🟢 Dokončeno", "0", "ukončeno dnes")

        layout.addWidget(self.overdue)
        layout.addWidget(self.waiting)
        layout.addWidget(self.today)
        layout.addWidget(self.done)

        self.refresh()

    def refresh(self):
        tasks = task_service.get_all_tasks()
        today = date.today()

        overdue = 0
        waiting = 0
        due_today = 0
        done_today = 0

        for task in tasks:
            status = task.computed_status

            if task.due_date and task.due_date < today and status not in ["Ukončeno", "Zrušeno"]:
                overdue += 1

            if status == "Splněno - čeká na kontrolu":
                waiting += 1

            if task.due_date == today and status not in ["Ukončeno", "Zrušeno"]:
                due_today += 1

            if task.checked_date == today or (task.completed_date == today and status == "Ukončeno"):
                done_today += 1

        self.overdue.set_value(str(overdue), "kritické věci k řešení")
        self.waiting.set_value(str(waiting), "čeká na kontrolu účinnosti")
        self.today.set_value(str(due_today), "termín splnění dnes")
        self.done.set_value(str(done_today), "ukončeno dnes")
