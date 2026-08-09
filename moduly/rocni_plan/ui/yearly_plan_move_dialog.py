"""Dialog přesunu položky Ročního plánu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QVBoxLayout

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rocni_plan.constants import (
    DIALOG_TITLE_MOVE,
    MAX_YEAR,
    MIN_YEAR,
    MONTH_NAMES,
)


class YearlyPlanMoveDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        from_year: int,
        from_month: int,
        default_year: int | None = None,
        default_month: int | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(DIALOG_TITLE_MOVE)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(360, 160)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.year_combo = QComboBox()
        for year in range(MIN_YEAR, MAX_YEAR + 1):
            self.year_combo.addItem(str(year), year)
        self.month_combo = QComboBox()
        for index, name in enumerate(MONTH_NAMES, start=1):
            self.month_combo.addItem(name, index)

        target_year = default_year if default_year is not None else from_year
        target_month = default_month if default_month is not None else from_month
        year_index = self.year_combo.findData(target_year)
        if year_index >= 0:
            self.year_combo.setCurrentIndex(year_index)
        month_index = self.month_combo.findData(target_month)
        if month_index >= 0:
            self.month_combo.setCurrentIndex(month_index)

        form.addRow("Cílový rok:", self.year_combo)
        form.addRow("Cílový měsíc:", self.month_combo)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self, is_new=False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        # Uložit → potvrzení přesunu; text tlačítka necháme standardní.
        layout.addWidget(buttons)

    def selected_year(self) -> int:
        return int(self.year_combo.currentData())

    def selected_month(self) -> int:
        return int(self.month_combo.currentData())
