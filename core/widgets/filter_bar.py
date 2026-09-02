from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QTableWidget, QWidget

ApplyFn = Callable[[str], tuple[int, int]]


class FilterBar(QWidget):
    """Globální živý filtr pro QTableWidget nebo vlastní apply_fn (strom)."""

    def __init__(
        self,
        table: QTableWidget | None = None,
        placeholder: str = "🔍 Hledat...",
        parent=None,
        *,
        apply_fn: ApplyFn | None = None,
    ):
        super().__init__(parent)

        self.table = table
        self._apply_fn = apply_fn

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(placeholder)

        self.count_label = QLabel("Zobrazeno: 0 / 0")
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(self.search_edit, 1)
        layout.addWidget(self.count_label)

        self.search_edit.textChanged.connect(self.apply_filter)

        self._esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self.search_edit)
        self._esc_shortcut.activated.connect(self.clear)

        self._focus_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._focus_shortcut.activated.connect(self.focus_filter)

        self.update_count()

    def focus_filter(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def clear(self) -> None:
        self.search_edit.clear()

    def apply_filter(self) -> None:
        text = self.search_edit.text().strip().lower()
        if self._apply_fn is not None:
            visible, total = self._apply_fn(text)
            self.count_label.setText(f"Zobrazeno: {visible} / {total}")
            return
        if self.table is None:
            self.count_label.setText("Zobrazeno: 0 / 0")
            return

        total = self.table.rowCount()
        visible = 0

        for row in range(total):
            row_text_parts = []

            for column in range(self.table.columnCount()):
                if self.table.isColumnHidden(column):
                    continue

                item = self.table.item(row, column)
                if item is not None:
                    row_text_parts.append(item.text())

            row_text = " ".join(row_text_parts).lower()
            match = text in row_text if text else True

            self.table.setRowHidden(row, not match)

            if match:
                visible += 1

        self.count_label.setText(f"Zobrazeno: {visible} / {total}")

    def update_count(self) -> None:
        self.apply_filter()
