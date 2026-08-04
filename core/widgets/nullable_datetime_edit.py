"""Volitelné datum a čas (prázdná hodnota je platná)."""

from __future__ import annotations

from datetime import datetime, time

from PySide6.QtCore import QDate, QDateTime, QPoint, QTime, Signal
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QHBoxLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.datetime_edit import DateTimeEdit

_DEFAULT_NEW_TIME = time(9, 0)


class NullableDateTimeEdit(QWidget):
    """Datum a čas s možností vymazání (rozpracované záznamy)."""

    dateTimeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.edit = DateTimeEdit()
        self.clear_button = QToolButton()
        self.clear_button.setText("✕")
        self.clear_button.setToolTip("Vymazat datum a čas")
        self.clear_button.setFixedSize(34, 34)

        self.set_button = QToolButton()
        self.set_button.setText("📅")
        self.set_button.setToolTip("Vybrat datum")
        self.set_button.setFixedSize(34, 34)

        layout.addWidget(self.edit, 1)
        layout.addWidget(self.set_button)
        layout.addWidget(self.clear_button)

        self._has_value = False
        self.edit.setEnabled(False)
        self.clear_button.clicked.connect(self.clear)
        self.set_button.clicked.connect(self.open_calendar)
        self.edit.dateTimeChanged.connect(self._on_edit_changed)

    def _on_edit_changed(self, *_args) -> None:
        if self._has_value:
            self.dateTimeChanged.emit()

    def open_calendar(self) -> None:
        """Otevře kalendář. Hodnotu nastaví až po výběru data; čas zachová."""
        if self._has_value:
            current = self.get_datetime()
            assert current is not None
            selected_date = current.date()
            keep_time = current.time()
        else:
            selected_date = datetime.now().date()
            keep_time = _DEFAULT_NEW_TIME

        dialog = QDialog(self)
        dialog.setWindowTitle("Vybrat datum")
        layout = QVBoxLayout(dialog)
        calendar = QCalendarWidget()
        calendar.setGridVisible(True)
        calendar.setSelectedDate(
            QDate(selected_date.year, selected_date.month, selected_date.day)
        )
        layout.addWidget(calendar)

        def use_selected_date() -> None:
            qdate = calendar.selectedDate()
            self.set_datetime(
                datetime(
                    qdate.year(),
                    qdate.month(),
                    qdate.day(),
                    keep_time.hour,
                    keep_time.minute,
                    keep_time.second,
                )
            )
            dialog.accept()

        calendar.clicked.connect(lambda *_args: use_selected_date())
        calendar.activated.connect(lambda *_args: use_selected_date())

        global_pos = self.mapToGlobal(QPoint(0, self.height()))
        dialog.move(global_pos)
        dialog.exec()

    def clear(self) -> None:
        self._has_value = False
        self.edit.setEnabled(False)
        self.dateTimeChanged.emit()

    def has_value(self) -> bool:
        return self._has_value

    def get_datetime(self) -> datetime | None:
        if not self._has_value:
            return None
        qdt = self.edit.dateTime()
        return datetime(
            qdt.date().year(),
            qdt.date().month(),
            qdt.date().day(),
            qdt.time().hour(),
            qdt.time().minute(),
            qdt.time().second(),
        )

    def set_datetime(self, value: datetime | None) -> None:
        if value is None:
            self.clear()
            return
        self._has_value = True
        self.edit.setEnabled(True)
        self.edit.setDateTime(
            QDateTime(
                QDate(value.year, value.month, value.day),
                QTime(value.hour, value.minute, value.second),
            )
        )
        self.dateTimeChanged.emit()
