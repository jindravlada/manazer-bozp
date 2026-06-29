from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns
from moduly.kontroly.sluzby.monthly_control_service import monthly_control_service
from moduly.kontroly.ui.control_summary_panel import ControlSummaryPanel
from moduly.kontroly.ui.control_year_matrix_table import ControlYearMatrixTable


class KontrolyPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Rok:"))
        self.year_combo = QComboBox()
        self._populate_year_combo()

        toolbar.addWidget(self.year_combo)
        toolbar.addStretch()

        self.summary_panel = ControlSummaryPanel()

        self.table = ControlYearMatrixTable()
        configure_table_columns(self.table, "controls_year_matrix")

        layout.addLayout(toolbar)
        layout.addWidget(self.summary_panel)
        layout.addWidget(self.table)

        self.year_combo.currentIndexChanged.connect(self.refresh)
        self.table.cellClicked.connect(self._on_cell_clicked)

        self.refresh()

    def _populate_year_combo(self):
        current_year = date.today().year
        self.year_combo.clear()
        for year in range(current_year - 2, current_year + 3):
            self.year_combo.addItem(str(year), year)
        self.year_combo.setCurrentText(str(current_year))

    def _selected_year(self) -> int:
        year = self.year_combo.currentData()
        if year is None:
            return int(self.year_combo.currentText())
        return int(year)

    def refresh(self):
        selected_year = self._selected_year()
        highlight_month = date.today().month if selected_year == date.today().year else None

        matrix = monthly_control_service.get_year_matrix(selected_year)
        self.table.set_highlight_month(highlight_month)
        self.table.load_matrix(matrix)
        configure_table_columns(self.table, "controls_year_matrix")
        self.summary_panel.set_highlight_month(highlight_month)
        self._update_summary(matrix)

    def _update_summary(self, matrix=None):
        if matrix is None:
            matrix = monthly_control_service.get_year_matrix(self._selected_year())
        summary = monthly_control_service.compute_summary(matrix)
        monthly = monthly_control_service.compute_monthly_summary(matrix)
        kl = monthly_control_service.compute_kl_summary(matrix)
        self.summary_panel.update_summary(summary, monthly, kl)

    def _on_cell_clicked(self, row: int, column: int):
        meta = self.table.cell_meta(row, column)
        if meta is None:
            return

        year = self._selected_year()
        thp_worker_id = meta["thp_worker_id"]
        item = self.table.item(row, column)
        if item is None:
            return

        if meta["part"] == "status":
            month = meta["month"]
            cell = monthly_control_service.cycle_status(year, month, thp_worker_id)
            self.table.apply_status_cell(item, cell.status)
            self._update_summary()
            return

        if meta["part"] == "kl":
            kl_index = meta["kl_index"]
            used = monthly_control_service.toggle_kl(year, thp_worker_id, kl_index)
            self.table.apply_kl_cell(item, kl_index, used)
            self._update_summary()
