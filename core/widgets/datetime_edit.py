from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QDateTimeEdit


class DateTimeEdit(QDateTimeEdit):
    """Jednotný výběr data a času v celé aplikaci."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.setDateTime(QDateTime.currentDateTime())

    def get_datetime_iso(self) -> str:
        return self.dateTime().toString("yyyy-MM-dd HH:mm:ss")

    def set_datetime_iso(self, value: str | None):
        if value:
            self.setDateTime(QDateTime.fromString(value, "yyyy-MM-dd HH:mm:ss"))
