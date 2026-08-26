"""Víceřádkové pole Souhrnné sdělení za okruh (Audit / Prověrka)."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QSizePolicy, QTextEdit, QVBoxLayout, QWidget

from core.shared.section_summary import SECTION_SUMMARY_LABEL

SUMMARY_EDIT_DEFAULT_HEIGHT = 160
SUMMARY_EDIT_COMPACT_HEIGHT = 110

_SUMMARY_MIN_HEIGHT = SUMMARY_EDIT_DEFAULT_HEIGHT


class _SummaryTextEdit(QTextEdit):
    """Kolečko rolí text jen při přetečení; jinak událost nechá rodiči."""

    def wheelEvent(self, event) -> None:
        bar = self.verticalScrollBar()
        if bar.maximum() <= bar.minimum():
            event.ignore()
            return
        super().wheelEvent(event)


class SectionSummaryEdit(QWidget):
    """Rozsáhlé textové pole společné pro Dokumentaci i Terén."""

    text_changed = Signal()

    def __init__(self, parent=None, *, compact: bool = False):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._label = QLabel(SECTION_SUMMARY_LABEL)
        self._label.setObjectName("SectionTitle")
        layout.addWidget(self._label)

        self._compact = bool(compact)
        self._edit = _SummaryTextEdit() if self._compact else QTextEdit()
        self._edit.setObjectName("SectionSummaryText")
        self._edit.setAcceptRichText(False)
        self._edit.setPlaceholderText("nepovinné")
        if self._compact:
            self._edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._edit.setFixedHeight(SUMMARY_EDIT_COMPACT_HEIGHT)
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Maximum,
            )
        else:
            self._edit.setMinimumHeight(_SUMMARY_MIN_HEIGHT)
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
