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

        self.overdue = DashboardCard("🔴 Po termínu", "0", "úkoly po termínu")
        self.today = DashboardCard("🔵 Dnes", "0", "úkoly na dnes")
        self.waiting = DashboardCard("🟡 Čeká kontrolu", "0", "splněno, čeká na ověření")
        self.open_total = DashboardCard("📋 Otevřeno", "0", "celkem otevřených úkolů")

        layout.addWidget(self.overdue)
        layout.addWidget(self.today)
        layout.addWidget(self.waiting)
        layout.addWidget(self.open_total)

        self.refresh()

    def refresh(self):
        tasks = task_service.get_all_tasks()
        today = date.today()

        overdue = 0
        waiting = 0
        due_today = 0
        open_total = 0

        for task in tasks:
            status = task.computed_status

            if status not in ["Ukončeno", "Zrušeno"]:
                open_total += 1

            if task.due_date and task.due_date < today and status not in ["Ukončeno", "Zrušeno"]:
                overdue += 1

            if status == "Splněno - čeká na kontrolu":
                waiting += 1

            if task.due_date == today and status not in ["Ukončeno", "Zrušeno"]:
                due_today += 1

        self.overdue.set_value(str(overdue), "úkoly po termínu")
        self.today.set_value(str(due_today), "úkoly na dnes")
        self.waiting.set_value(str(waiting), "čeká na kontrolu účinnosti")
        self.open_total.set_value(str(open_total), "celkem otevřených úkolů")
