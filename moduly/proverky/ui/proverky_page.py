from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.proverky.constants import (
    DEFAULT_INSPECTION_STATUS_FILTER,
    INSPECTION_STATUS_BY_FILTER,
    INSPECTION_STATUS_FILTER_DOKONCENE,
    INSPECTION_STATUS_FILTER_PLANOVANE,
    INSPECTION_STATUS_FILTER_PROBIHAJICI,
    INSPECTION_STATUS_FILTER_VSE,
    YEAR_FILTER_VSE,
)
from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog
from moduly.proverky.ui.bozp_inspection_table import BozpInspectionTable
from moduly.proverky.ui.rocni_plan_dialog import RocniPlanDialog
from moduly.proverky.ui.rocni_zprava_dialog import RocniZpravaDialog


class ProverkyPage(QWidget):
    """Hlavní stránka modulu Prověrky BOZP — kostra bez persistence."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nová prověrka")
        self.plan_btn = QPushButton("Roční plán")
        self.report_btn = QPushButton("Roční zpráva")

        self.status_filter = QComboBox()
        self.status_filter.addItems([
            INSPECTION_STATUS_FILTER_PROBIHAJICI,
            INSPECTION_STATUS_FILTER_PLANOVANE,
            INSPECTION_STATUS_FILTER_DOKONCENE,
            INSPECTION_STATUS_FILTER_VSE,
        ])
        self.status_filter.setCurrentText(DEFAULT_INSPECTION_STATUS_FILTER)

        self.year_filter = QComboBox()
        self._populate_year_filter()

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.plan_btn)
        toolbar.addWidget(self.report_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Stav:"))
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(QLabel("Rok:"))
        toolbar.addWidget(self.year_filter)

        self.table = BozpInspectionTable()
        configure_table_columns(self.table, "bozp_inspections")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat prověrku...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_inspection)
        self.plan_btn.clicked.connect(self.show_annual_plan)
        self.report_btn.clicked.connect(self.show_annual_report)
        self.table.doubleClicked.connect(self.open_selected_inspection)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.year_filter.currentIndexChanged.connect(self.refresh)

        self.refresh()

    def refresh(self) -> None:
        inspections = self._filter_inspections([])
        self.table.load_inspections(inspections)
        configure_table_columns(self.table, "bozp_inspections")
        self.text_filter.update_count()

    def _populate_year_filter(self) -> None:
        current_year = date.today().year

        self.year_filter.blockSignals(True)
        self.year_filter.clear()
        self.year_filter.addItem(str(current_year), current_year)
        self.year_filter.addItem(YEAR_FILTER_VSE, YEAR_FILTER_VSE)
        self.year_filter.setCurrentIndex(0)
        self.year_filter.blockSignals(False)

    def _filter_inspections(self, inspections):
        mode = self.status_filter.currentText()
        if mode != INSPECTION_STATUS_FILTER_VSE:
            status = INSPECTION_STATUS_BY_FILTER.get(mode)
            if status is not None:
                inspections = [
                    inspection for inspection in inspections
                    if getattr(inspection, "status", None) == status
                ]

        year_value = self.year_filter.currentData()
        if year_value != YEAR_FILTER_VSE:
            inspections = [
                inspection for inspection in inspections
                if getattr(inspection, "inspection_date", None) is not None
                and inspection.inspection_date.year == year_value
            ]

        return inspections

    def new_inspection(self) -> None:
        dialog = BozpInspectionDialog(self)
        exec_maximized(dialog)

    def open_selected_inspection(self) -> None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return

        dialog = BozpInspectionDialog(self)
        exec_maximized(dialog)

    def open_inspection(self, _inspection_id: int) -> None:
        """Hook pro budoucí navigaci ze zdrojových záznamů."""
        dialog = BozpInspectionDialog(self)
        exec_maximized(dialog)

    def show_annual_plan(self) -> None:
        exec_maximized(RocniPlanDialog(self))

    def show_annual_report(self) -> None:
        exec_maximized(RocniZpravaDialog(self))
