from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from core.dashboard.widget_base import DashboardPanel
from moduly.kniha_urazu.sluzby.accident_service import accident_service


class DaysWithoutAccidentWidget(DashboardPanel):
    def __init__(self, compact=False):
        super().__init__("" if compact else "Dny bez pracovního úrazu")
        self.compact = compact
        self.content = QLabel()
        self.content.setWordWrap(True)
        self.content.setTextFormat(Qt.RichText)
        self.layout.addWidget(self.content)
        if compact:
            self.title_label.hide()
            self.setFixedHeight(100)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.refresh()

    def _last_accident_date(self) -> date | None:
        return accident_service.get_last_accident_date()

    def refresh(self):
        last_date = self._last_accident_date()
        if last_date is None:
            self.content.setText("Dosud není evidován žádný pracovní úraz.")
            return

        days = (date.today() - last_date).days
        if self.compact:
            self.content.setText(
                f"<b>{days} dnů bez pracovního úrazu</b><br>"
                f"<b>Poslední úraz: {last_date.strftime('%d.%m.%Y')}</b>"
            )
            return

        self.content.setText(
            f"Počet dnů bez pracovního úrazu: <b>{days}</b><br>"
            f"Datum posledního pracovního úrazu: <b>{last_date.strftime('%d.%m.%Y')}</b>"
        )
