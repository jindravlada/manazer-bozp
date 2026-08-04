"""Volitelné datum a čas (prázdná hodnota je platná)."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDateTime, Signal
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from core.widgets.datetime_edit import DateTimeEdit


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

        layout.addWidget(self.edit, 1)
        layout.addWidget(self.clear_button)

        self._has_value = False
        self.edit.setEnabled(False)
        self.clear_button.clicked.connect(self.clear)
        self.edit.dateTimeChanged.connect(self._on_edit_changed)

        set_btn = QToolButton()
        set_btn.setText("📅")
        set_btn.setToolTip("Nastavit datum a čas")
        set_btn.setFixedSize(34, 34)
        set_btn.clicked.connect(self._ensure_value)
        layout.insertWidget(1, set_btn)
        self.set_button = set_btn

    def _on_edit_changed(self, *_args) -> None:
        if self._has_value:
            self.dateTimeChanged.emit()

    def _ensure_value(self) -> None:
        if not self._has_value:
            self._has_value = True
            self.edit.setEnabled(True)
            self.edit.setDateTime(QDateTime.currentDateTime())
        self.dateTimeChanged.emit()

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
            QDateTime(value.year, value.month, value.day, value.hour, value.minute, value.second)
        )
        self.dateTimeChanged.emit()
