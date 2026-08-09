"""Jednoduchý výběr měsíce pro akci Měsíc zpracován."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QVBoxLayout

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rocni_plan.constants import (
    ACTION_MARK_MONTH_PROCESSED,
    MONTH_NAMES,
)


class YearlyPlanMonthPickDialog(QDialog):
    def __init__(self, parent=None, *, default_month: int | None = None):
        super().__init__(parent)
        self.setWindowTitle(ACTION_MARK_MONTH_PROCESSED)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(320, 140)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.month_combo = QComboBox()
        for index, name in enumerate(MONTH_NAMES, start=1):
            self.month_combo.addItem(name.capitalize(), index)
        month = default_month if default_month is not None else 1
        month_index = self.month_combo.findData(month)
        if month_index >= 0:
            self.month_combo.setCurrentIndex(month_index)
        form.addRow("Měsíc:", self.month_combo)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self, is_new=False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_month(self) -> int:
        return int(self.month_combo.currentData())
