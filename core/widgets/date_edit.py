from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDateEdit


class DateEdit(QDateEdit):
    """Jednotný výběr data v celé aplikaci. Český formát DD.MM.YYYY."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd.MM.yyyy")
        self.setDate(QDate.currentDate())

    def get_date_iso(self) -> str:
        return self.date().toString("yyyy-MM-dd")

    def set_date_iso(self, value: str | None):
        if value:
            self.setDate(QDate.fromString(value, "yyyy-MM-dd"))
