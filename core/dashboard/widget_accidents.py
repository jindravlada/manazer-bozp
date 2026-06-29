from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton

from core.dashboard.widget_base import DashboardPanel
from moduly.kniha_urazu.sluzby.accident_service import accident_service


class AccidentsWidget(DashboardPanel):
    def __init__(self, open_kniha_urazu_callback=None):
        super().__init__("Pracovní úrazy")
        self.open_kniha_urazu_callback = open_kniha_urazu_callback

        self.content = QLabel()
        self.content.setWordWrap(True)
        self.content.setTextFormat(Qt.TextFormat.RichText)
        self.content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.open_button = QPushButton("Otevřít Knihu úrazů")
        if self.open_kniha_urazu_callback:
            self.open_button.clicked.connect(self.open_kniha_urazu_callback)

        self.layout.addWidget(self.content)
        self.layout.addWidget(self.open_button)

        self.refresh()

    def refresh(self):
        summary = accident_service.get_dashboard_summary()

        if not summary.has_accidents:
            self.content.setText("Nebyl evidován žádný pracovní úraz.")
            return

        self.content.setText(
            f"Celkem letos: <b>{summary.total_this_year}</b><br>"
            f"Posledních 30 dní: <b>{summary.last_30_days}</b><br>"
            f"Dny bez pracovního úrazu: <b>{summary.days_without_accident}</b>"
        )
