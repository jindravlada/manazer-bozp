"""Volitelný čas (prázdná hodnota je platná) s zápisem z klávesnice."""

from __future__ import annotations

from datetime import time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QToolButton, QWidget


def parse_czech_time(text: str) -> time | None:
    """Parsování běžných zápisů času: 9, 9:30, 09:30, 930, 1430."""
    raw = (text or "").strip()
    if not raw:
        return None

    if ":" in raw:
        parts = raw.split(":")
        if len(parts) != 2:
            return None
        try:
            hour = int(parts[0])
            minute = int(parts[1] or "0")
            return time(hour, minute)
        except ValueError:
            return None

    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    try:
        if len(digits) <= 2:
            return time(int(digits), 0)
        if len(digits) == 3:
            return time(int(digits[0]), int(digits[1:3]))
        if len(digits) == 4:
            return time(int(digits[0:2]), int(digits[2:4]))
    except ValueError:
        return None
    return None


class NullableTimeEdit(QWidget):
    """Čas HH:mm s možností vymazání."""

    timeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("hh:mm")
        self.line_edit.setMinimumHeight(34)
        self.line_edit.setMaximumWidth(90)

        self.clear_button = QToolButton()
        self.clear_button.setText("✕")
        self.clear_button.setToolTip("Vymazat čas")
        self.clear_button.setFixedSize(34, 34)

        layout.addWidget(self.line_edit, 1)
        layout.addWidget(self.clear_button)

        self.clear_button.clicked.connect(self.clear_time)
        self.line_edit.editingFinished.connect(self._normalize_input)

    def _normalize_input(self) -> None:
        text = self.line_edit.text().strip()
        if not text:
            self.timeChanged.emit()
            return
        parsed = parse_czech_time(text)
        if parsed is None:
            return
        self.set_time_value(parsed)

    def clear_time(self) -> None:
        self.line_edit.clear()
        self.timeChanged.emit()

    def has_time(self) -> bool:
        return self.get_time() is not None

    def get_time(self) -> time | None:
        text = self.line_edit.text().strip()
        if not text:
            return None
        return parse_czech_time(text)

    def set_time_value(self, value: time | None) -> None:
        if value is None:
            self.line_edit.clear()
        else:
            self.line_edit.setText(f"{value.hour:02d}:{value.minute:02d}")
        self.timeChanged.emit()
