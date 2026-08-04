"""Oddělená pole data a času pro editor události."""

from __future__ import annotations

from datetime import datetime, time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.nullable_time_edit import NullableTimeEdit

_DEFAULT_TIME = time(9, 0)


class EventDateTimeFields(QWidget):
    """Datum + čas vedle sebe; kalendář jen jako pomocník."""

    dateTimeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppress = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.date_edit = NullableDateEdit()
        self.time_edit = NullableTimeEdit()
        layout.addWidget(self.date_edit, 1)
        layout.addWidget(self.time_edit, 0)

        self.date_edit.dateChanged.connect(self._on_part_changed)
        self.time_edit.timeChanged.connect(self._on_part_changed)

    def _on_part_changed(self) -> None:
        if self._suppress:
            return
        self.dateTimeChanged.emit()

    def has_value(self) -> bool:
        return self.date_edit.has_date()

    def get_datetime(self) -> datetime | None:
        day = self.date_edit.get_date()
        if day is None:
            return None
        clock = self.time_edit.get_time() or _DEFAULT_TIME
        return datetime(day.year, day.month, day.day, clock.hour, clock.minute)

    def set_datetime(self, value: datetime | None) -> None:
        self._suppress = True
        if value is None:
            self.date_edit.clear_date()
            self.time_edit.clear_time()
        else:
            # Datum a čas nastavit odděleně – změna data čas nepřepisuje.
            self.date_edit.set_date_value(value.date())
            self.time_edit.set_time_value(value.time().replace(second=0, microsecond=0))
        self._suppress = False
        self.dateTimeChanged.emit()

    def clear(self) -> None:
        self.set_datetime(None)
