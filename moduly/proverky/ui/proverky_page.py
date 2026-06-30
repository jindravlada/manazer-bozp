from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
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
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog
from moduly.proverky.ui.bozp_inspection_table import BozpInspectionTable
from moduly.proverky.ui.rocni_plan_dialog import RocniPlanDialog
from moduly.proverky.ui.rocni_zprava_dialog import RocniZpravaDialog


class _InspectionRow:
    def __init__(self, inspection):
        self.id = inspection.id
        self.number = inspection.number
        self.inspection_date = inspection.inspection_date
        self.workplace_name = inspection.workplace_name
        self.lead_inspector_name = ""
        self.findings_count = bozp_inspection_service.findings_count(inspection.id)
        self.status = inspection.status
        self.title = inspection.title


class ProverkyPage(QWidget):
    """Hlavní stránka modulu Prověrky BOZP."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nová prověrka")
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")
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
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
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
        self.edit_btn.clicked.connect(self.open_selected_inspection)
        self.delete_btn.clicked.connect(self.delete_selected_inspection)
        self.plan_btn.clicked.connect(self.show_annual_plan)
        self.report_btn.clicked.connect(self.show_annual_report)
        self.table.doubleClicked.connect(self.open_selected_inspection)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.year_filter.currentIndexChanged.connect(self.refresh)

        self.refresh()

    def refresh(self) -> None:
        inspections = self._filter_inspections(bozp_inspection_service.get_all())
        rows = [_InspectionRow(inspection) for inspection in inspections]
        self.table.load_inspections(rows)
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
                    if inspection.status == status
                ]

        year_value = self.year_filter.currentData()
        if year_value != YEAR_FILTER_VSE:
            inspections = [
                inspection for inspection in inspections
                if (
                    (inspection.inspection_date is not None and inspection.inspection_date.year == year_value)
                    or (inspection.inspection_date is None and inspection.year == year_value)
                )
            ]

        return inspections

    def _selected_inspection_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def new_inspection(self) -> None:
        dialog = BozpInspectionDialog(self)
        if exec_maximized(dialog):
            data = dialog.get_data()
            workplace_name = bozp_inspection_service.resolve_workplace_name(data.pop("workplace_id"))
            bozp_inspection_service.create_inspection(workplace_name=workplace_name, **data)
            self.refresh()

    def open_selected_inspection(self) -> None:
        inspection_id = self._selected_inspection_id()
        if inspection_id is None:
            QMessageBox.information(self, "Prověrky BOZP", "Vyberte prověrku.")
            return

        self.open_inspection(inspection_id)

    def open_inspection(self, inspection_id: int) -> None:
        inspection = bozp_inspection_service.get_by_id(inspection_id)
        if inspection is None:
            QMessageBox.warning(self, "Prověrky BOZP", "Prověrka nebyla nalezena.")
            self.refresh()
            return

        dialog = BozpInspectionDialog(self, inspection=inspection)
        if exec_maximized(dialog):
            data = dialog.get_data()
            workplace_name = bozp_inspection_service.resolve_workplace_name(data.pop("workplace_id"))
            bozp_inspection_service.update_inspection(inspection_id, workplace_name=workplace_name, **data)
            self.refresh()

    def delete_selected_inspection(self) -> None:
        inspection_id = self._selected_inspection_id()
        if inspection_id is None:
            QMessageBox.information(self, "Prověrky BOZP", "Vyberte prověrku.")
            return

        inspection = bozp_inspection_service.get_by_id(inspection_id)
        if inspection is None:
            QMessageBox.warning(self, "Prověrky BOZP", "Prověrka nebyla nalezena.")
            self.refresh()
            return

        answer = QMessageBox.question(
            self,
            "Smazat prověrku",
            f"Opravdu smazat prověrku {inspection.number or inspection_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            bozp_inspection_service.delete_inspection(inspection_id)
            self.refresh()

    def show_annual_plan(self) -> None:
        exec_maximized(RocniPlanDialog(self))

    def show_annual_report(self) -> None:
        exec_maximized(RocniZpravaDialog(self))
