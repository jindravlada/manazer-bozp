from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from core.dashboard.widget_base import DashboardPanel
from moduly.ukoly.sluzby.task_service import task_service


class StatisticsPlaceholderWidget(DashboardPanel):
    def __init__(self):
        super().__init__("Statistiky")
        self.content = QLabel()
        self.content.setWordWrap(True)
        self.content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(130)
        self.layout.addWidget(self.content)
        self.layout.addStretch(1)
        self.refresh()

    def refresh(self):
        tasks = task_service.get_all_tasks()
        active = len([task for task in tasks if task.computed_status not in ["Ukončeno", "Zrušeno"]])
        done = len([task for task in tasks if task.computed_status == "Ukončeno"])
        canceled = len([task for task in tasks if task.computed_status == "Zrušeno"])

        self.content.setText(
            f"📋 Aktivní opatření: <b>{active}</b><br>"
            f"✅ Ukončená opatření: <b>{done}</b><br>"
            f"⚪ Zrušená opatření: <b>{canceled}</b><br>"
        )
