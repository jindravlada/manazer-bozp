from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy

from core.dashboard.widget_base import DashboardPanel
from moduly.kontroly.sluzby.monthly_control_service import monthly_control_service


class ControlsWidget(DashboardPanel):
    def __init__(self, open_kontroly_callback=None):
        super().__init__("Kontroly – aktuální měsíc")
        self.open_kontroly_callback = open_kontroly_callback

        self.content = QLabel()
        self.content.setWordWrap(True)
        self.content.setTextFormat(Qt.TextFormat.RichText)
        self.content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.open_button = QPushButton("Otevřít Kontroly")
        if self.open_kontroly_callback:
            self.open_button.clicked.connect(self.open_kontroly_callback)

        self.layout.addWidget(self.content, 1)
        self.layout.addSpacing(4)
        self.layout.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignBottom)

        self.setMinimumHeight(220)
        self.refresh()

    def refresh(self):
        today = date.today()
        matrix = monthly_control_service.get_year_matrix(today.year)
        thp_count = len(matrix)

        if thp_count == 0:
            self.content.setText("Nejsou nastaveni THP pro kontroly.")
            return

        monthly = monthly_control_service.compute_monthly_summary(matrix)
        month_index = today.month - 1
        done_count = monthly.done_by_month[month_index]
        none_count = monthly.none_by_month[month_index]
        defect_count = monthly.defect_by_month[month_index]
        excused_count = monthly.excused_by_month[month_index]
        percent = round(done_count * 100 / thp_count) if thp_count else 0

        self.content.setText(
            f"THP: <b>{thp_count}</b><br>"
            f"Provedeno: <b>{done_count} / {thp_count}</b> ({percent} %)<br>"
            f"Chybí: <b>{none_count}</b><br>"
            f"Omluveno: <b>{excused_count}</b><br>"
            f"Se závadou: <b>{defect_count}</b>"
        )
