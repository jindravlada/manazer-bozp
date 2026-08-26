"""Víceřádkové pole Souhrnné sdělení za okruh (Audit / Prověrka)."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from core.shared.section_summary import SECTION_SUMMARY_LABEL

_SUMMARY_MIN_HEIGHT = 160


class SectionSummaryEdit(QWidget):
    """Rozsáhlé textové pole (6–8 řádků) společné pro Dokumentaci i Terén."""

    text_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._label = QLabel(SECTION_SUMMARY_LABEL)
        self._label.setObjectName("SectionTitle")
        layout.addWidget(self._label)

        self._edit = QTextEdit()
        self._edit.setAcceptRichText(False)
        self._edit.setMinimumHeight(_SUMMARY_MIN_HEIGHT)
        self._edit.setPlaceholderText("nepovinné")
        self._edit.textChanged.connect(self.text_changed.emit)
        layout.addWidget(self._edit)

    def set_text(self, value: str) -> None:
        blocked = self._edit.blockSignals(True)
        try:
            self._edit.setPlainText(value or "")
        finally:
            self._edit.blockSignals(blocked)

    def text(self) -> str:
        return self._edit.toPlainText()
