from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


class AccidentTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(11)
        self.setHorizontalHeaderLabels([
            "",
            "ID",
            "Číslo",
            "Datum úrazu",
            "Zraněný",
            "Pracovní pozice",
            "Vedoucí zaměstnanec",
            "Pracoviště",
            "Místo úrazu",
            "ZoÚ",
            "Op.",
        ])

        self.setColumnHidden(1, True)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

    def load_accidents(self, accidents):
        self.setRowCount(len(accidents))

        for row, accident in enumerate(accidents):
            values = [
                "",
                str(accident.id),
                accident.number or "—",
                "" if accident.accident_date is None else accident.accident_date.strftime("%d.%m.%Y"),
                accident.employee_name or "—",
                accident.druh_vykonavane_prace or "—",
                accident.zapsal_jmeno or "—",
                accident.workplace_name or accident.pracoviste or "—",
                accident.misto_urazu or "—",
                "",
                "",
            ]

            tooltip = self._tooltip(accident)

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)

                if column == 0:
                    item.setBackground(self._injury_type_color(accident.druh_urazu or ""))

                self.setItem(row, column, item)

    def _injury_type_color(self, druh_urazu: str) -> QColor:
        text = (druh_urazu or "").lower()

        if "smrteln" in text:
            return QColor("#222222")
        if "závaž" in text or "zavaz" in text:
            return QColor("#d32f2f")
        if "delší než 3" in text or "delsi nez 3" in text:
            return QColor("#ff9800")
        if "nepřesahující 3" in text or "nepresahujici 3" in text:
            return QColor("#2e7d32")

        return QColor("#e0e0e0")

    def _tooltip(self, accident):
        datum = "" if accident.accident_date is None else accident.accident_date.strftime("%d.%m.%Y")
        return (
            f"Pracovní úraz {accident.number or '—'}\n"
            f"Datum: {datum} {accident.accident_time or ''}\n"
            f"Zaměstnanec: {accident.employee_name or '—'}\n"
            f"Pracoviště: {accident.workplace_name or accident.pracoviste or '—'}\n"
            f"Druh úrazu: {accident.druh_urazu or '—'}\n\n"
            f"{accident.popis_urazoveho_deje or ''}"
        )
