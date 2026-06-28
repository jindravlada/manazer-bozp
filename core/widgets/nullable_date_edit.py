from datetime import date

from PySide6.QtCore import QDate, QPoint, Signal
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class NullableDateEdit(QWidget):
    """
    Datum s prázdnou hodnotou.

    Formát pro ČR:
    DD.MM.YYYY
    """

    dateChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("dd.mm.rrrr")
        self.line_edit.setMinimumHeight(34)

        self.calendar_button = QToolButton()
        self.calendar_button.setText("📅")
        self.calendar_button.setToolTip("Vybrat datum")
        self.calendar_button.setFixedSize(34, 34)

        self.clear_button = QToolButton()
        self.clear_button.setText("✕")
        self.clear_button.setToolTip("Vymazat datum")
        self.clear_button.setFixedSize(34, 34)

        button_style = """
            QToolButton {
                font-size: 16px;
                padding: 0px;
            }
        """
        self.calendar_button.setStyleSheet(button_style)
        self.clear_button.setStyleSheet(button_style)

        layout.addWidget(self.line_edit, 1)
        layout.addWidget(self.calendar_button)
        layout.addWidget(self.clear_button)

        self.calendar_button.clicked.connect(self.open_calendar)
        self.clear_button.clicked.connect(self.clear_date)
        self.line_edit.editingFinished.connect(self._normalize_input)

    def _normalize_input(self):
        text = self.line_edit.text().strip()

        if not text:
            self.dateChanged.emit()
            return

        parsed = self._parse_date(text)
        if parsed is None:
            return

        self.set_date_value(parsed)

    def _parse_date(self, text: str) -> date | None:
        text = text.strip()

        if "." in text:
            parts = text.split(".")
            if len(parts) == 3:
                try:
                    day = int(parts[0])
                    month = int(parts[1])
                    year = int(parts[2])
                    if year < 100:
                        year += 2000
                    return date(year, month, day)
                except ValueError:
                    return None

        digits = "".join(ch for ch in text if ch.isdigit())

        if len(digits) == 8:
            try:
                return date(int(digits[4:8]), int(digits[2:4]), int(digits[0:2]))
            except ValueError:
                return None

        if len(digits) == 6:
            try:
                return date(2000 + int(digits[4:6]), int(digits[2:4]), int(digits[0:2]))
            except ValueError:
                return None

        if len(digits) == 4:
            try:
                return date(2000 + int(digits[2:4]), int(digits[1:2]), int(digits[0:1]))
            except ValueError:
                return None

        return None

    def open_calendar(self):
        selected_date = self.get_date() or date.today()

        dialog = QDialog(self)
        dialog.setWindowTitle("Vybrat datum")

        layout = QVBoxLayout(dialog)
        calendar = QCalendarWidget()
        calendar.setGridVisible(True)
        calendar.setSelectedDate(
            QDate(selected_date.year, selected_date.month, selected_date.day)
        )

        layout.addWidget(calendar)

        def use_selected_date():
            qdate = calendar.selectedDate()
            self.set_date_value(date(qdate.year(), qdate.month(), qdate.day()))
            dialog.accept()

        calendar.clicked.connect(lambda _: use_selected_date())
        calendar.activated.connect(lambda _: use_selected_date())

        global_pos = self.mapToGlobal(QPoint(0, self.height()))
        dialog.move(global_pos)
        dialog.exec()

    def clear_date(self):
        self.line_edit.clear()
        self.dateChanged.emit()

    def has_date(self) -> bool:
        return self.get_date() is not None

    def get_date(self) -> date | None:
        text = self.line_edit.text().strip()
        if not text:
            return None

        return self._parse_date(text)

    def set_date_value(self, value):
        if value:
            self.line_edit.setText(value.strftime("%d.%m.%Y"))
        else:
            self.line_edit.clear()

        self.dateChanged.emit()

    def set_date_iso(self, value: str | None):
        if not value:
            self.clear_date()
            return

        try:
            year, month, day = [int(part) for part in value.split("-")]
            self.set_date_value(date(year, month, day))
        except ValueError:
            self.clear_date()
