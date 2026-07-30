from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
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
    INSPECTION_DETAILED_REPORT_BUTTON_LABEL,
    INSPECTION_DETAILED_REPORT_DIALOG_TITLE,
    INSPECTION_DETAILED_REPORT_REQUIRES_COMPLETED,
    INSPECTION_DETAILED_REPORT_TOOLTIP,
    INSPECTION_PROTOCOL_BUTTON_LABEL,
    INSPECTION_PROTOCOL_DIALOG_TITLE,
    INSPECTION_PROTOCOL_REQUIRES_COMPLETED,
    INSPECTION_PROTOCOL_TOOLTIP,
    INSPECTION_STATUS_BY_FILTER,
    INSPECTION_STATUS_DOKONCENO,
    INSPECTION_STATUS_FILTER_DOKONCENE,
    INSPECTION_STATUS_FILTER_PLANOVANE,
    INSPECTION_STATUS_FILTER_PROBIHAJICI,
    INSPECTION_STATUS_FILTER_VSE,
    KNOWLEDGE_EDITOR_BUTTON_LABEL,
    MODULE_NAME,
    YEAR_FILTER_VSE,
)
from moduly.proverky.ui.proverky_knowledge_editor_dialog import ProverkyKnowledgeEditorDialog
from moduly.proverky.sluzby.bozp_inspection_commission_service import (
    bozp_inspection_commission_service,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service
from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog
from moduly.proverky.ui.bozp_inspection_table import BozpInspectionTable
from moduly.proverky.ui.generate_inspections_dialog import GenerateInspectionsDialog
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
        self.generate_btn = QPushButton("Generovat prověrky")
        self.protocol_btn = QPushButton(INSPECTION_PROTOCOL_BUTTON_LABEL)
        self.protocol_btn.setEnabled(False)
        self.protocol_btn.setToolTip(INSPECTION_PROTOCOL_TOOLTIP)
        self.detailed_report_btn = QPushButton(INSPECTION_DETAILED_REPORT_BUTTON_LABEL)
        self.detailed_report_btn.setEnabled(False)
        self.detailed_report_btn.setToolTip(INSPECTION_DETAILED_REPORT_TOOLTIP)
        self.report_btn = QPushButton("Roční zpráva")
        self.report_btn.setToolTip("Roční zpráva o stavu BOZP za vybraný kalendářní rok.")
        self.knowledge_editor_btn = QPushButton(KNOWLEDGE_EDITOR_BUTTON_LABEL)

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
        toolbar.addWidget(self.generate_btn)
        toolbar.addWidget(self.protocol_btn)
        toolbar.addWidget(self.detailed_report_btn)
        toolbar.addWidget(self.report_btn)
        toolbar.addWidget(self.knowledge_editor_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Stav:"))
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(QLabel("Rok:"))
        toolbar.addWidget(self.year_filter)

        self.table = BozpInspectionTable()
        configure_table_columns(self.table, "bozp_inspections")
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat prověrku...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_inspection)
        self.edit_btn.clicked.connect(self.open_selected_inspection)
        self.delete_btn.clicked.connect(self.delete_selected_inspection)
        self.plan_btn.clicked.connect(self.show_annual_plan)
        self.generate_btn.clicked.connect(self.generate_inspections)
        self.protocol_btn.clicked.connect(self.export_selected_protocol)
        self.detailed_report_btn.clicked.connect(self.export_selected_detailed_report)
        self.report_btn.clicked.connect(self.show_annual_report)
        self.knowledge_editor_btn.clicked.connect(self.open_knowledge_editor)
        self.table.doubleClicked.connect(self.open_selected_inspection)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(
            self._update_export_actions
        )
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.year_filter.currentIndexChanged.connect(self.refresh)

        self.refresh()

    def refresh(self) -> None:
        inspections = self._filter_inspections(bozp_inspection_service.get_all())
        rows = [_InspectionRow(inspection) for inspection in inspections]
        self.table.load_inspections(rows)
        configure_table_columns(self.table, "bozp_inspections")
        self.text_filter.update_count()
        self._update_export_actions()

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

    def _selected_inspection(self):
        inspection_id = self._selected_inspection_id()
        if inspection_id is None:
            return None
        return bozp_inspection_service.get_by_id(inspection_id)

    def _update_export_actions(self, *_args) -> None:
        inspection = self._selected_inspection()
        completed = (
            inspection is not None
            and inspection.status == INSPECTION_STATUS_DOKONCENO
        )
        self.protocol_btn.setEnabled(completed)
        self.detailed_report_btn.setEnabled(completed)

    def _show_table_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if not index.isValid():
            return

        self.table.selectRow(index.row())
        menu = QMenu(self)
        menu.addAction("Upravit", self.open_selected_inspection)
        menu.addAction("Smazat", self.delete_selected_inspection)

        inspection = self._selected_inspection()
        if inspection is not None and inspection.status == INSPECTION_STATUS_DOKONCENO:
            menu.addSeparator()
            menu.addAction(
                INSPECTION_PROTOCOL_BUTTON_LABEL,
                self.export_selected_protocol,
            )
            menu.addAction(
                INSPECTION_DETAILED_REPORT_BUTTON_LABEL,
                self.export_selected_detailed_report,
            )

        menu.exec(self.table.viewport().mapToGlobal(position))

    def _prepare_spis_data(self, data: dict) -> dict:
        payload = {key: value for key, value in data.items() if key != "commission_members"}

        workplace_id = payload.get("workplace_id")
        if workplace_id is None:
            workplace_id = bozp_inspection_service.resolve_workplace_id_by_name(
                payload.get("workplace_name", "")
            )
            payload["workplace_id"] = workplace_id
        payload["workplace_name"] = bozp_inspection_service.resolve_workplace_name(workplace_id)
        return payload

    def _save_commission_members(self, inspection_id: int, data: dict) -> None:
        members = data.get("commission_members")
        if members is None:
            return
        bozp_inspection_commission_service.save_members(inspection_id, members)

    def new_inspection(self) -> None:
        dialog = BozpInspectionDialog(self)
        if exec_maximized(dialog):
            data = dialog.get_data()
            inspection = bozp_inspection_service.create_inspection(**self._prepare_spis_data(data))
            self._save_commission_members(inspection.id, data)
            self.refresh()

    def open_selected_inspection(self) -> None:
        inspection_id = self._selected_inspection_id()
        if inspection_id is None:
            QMessageBox.information(self, MODULE_NAME, "Vyberte prověrku.")
            return

        self.open_inspection(inspection_id)

    def open_inspection(self, inspection_id: int) -> None:
        inspection = bozp_inspection_service.get_by_id(inspection_id)
        if inspection is None:
            QMessageBox.warning(self, MODULE_NAME, "Prověrka nebyla nalezena.")
            self.refresh()
            return

        dialog = BozpInspectionDialog(self, inspection=inspection)
        if exec_maximized(dialog):
            data = dialog.get_data()
            bozp_inspection_service.update_inspection(
                inspection_id,
                **self._prepare_spis_data(data),
            )
            self._save_commission_members(inspection_id, data)
            self.refresh()

    def export_selected_protocol(self) -> None:
        inspection = self._selected_inspection()
        if inspection is None:
            QMessageBox.information(
                self, INSPECTION_PROTOCOL_DIALOG_TITLE, "Vyberte prověrku."
            )
            return
        if inspection.status != INSPECTION_STATUS_DOKONCENO:
            QMessageBox.information(
                self,
                INSPECTION_PROTOCOL_DIALOG_TITLE,
                INSPECTION_PROTOCOL_REQUIRES_COMPLETED,
            )
            self._update_export_actions()
            return

        try:
            protokol_proverky_service.open_for_inspection(inspection)
        except Exception as exc:
            QMessageBox.warning(
                self,
                INSPECTION_PROTOCOL_DIALOG_TITLE,
                f"Zprávu se nepodařilo vygenerovat.\n\n{exc}",
            )

    def export_selected_detailed_report(self) -> None:
        inspection = self._selected_inspection()
        if inspection is None:
            QMessageBox.information(
                self,
                INSPECTION_DETAILED_REPORT_DIALOG_TITLE,
                "Vyberte prověrku.",
            )
            return
        if inspection.status != INSPECTION_STATUS_DOKONCENO:
            QMessageBox.information(
                self,
                INSPECTION_DETAILED_REPORT_DIALOG_TITLE,
                INSPECTION_DETAILED_REPORT_REQUIRES_COMPLETED,
            )
            self._update_export_actions()
            return

        try:
            protokol_proverky_service.open_detailed_report_for_inspection(inspection)
        except Exception as exc:
            QMessageBox.warning(
                self,
                INSPECTION_DETAILED_REPORT_DIALOG_TITLE,
                f"Podrobnou zprávu se nepodařilo vygenerovat.\n\n{exc}",
            )

    def delete_selected_inspection(self) -> None:
        inspection_id = self._selected_inspection_id()
        if inspection_id is None:
            QMessageBox.information(self, MODULE_NAME, "Vyberte prověrku.")
            return

        inspection = bozp_inspection_service.get_by_id(inspection_id)
        if inspection is None:
            QMessageBox.warning(self, MODULE_NAME, "Prověrka nebyla nalezena.")
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
        year_value = self.year_filter.currentData()
        if year_value == YEAR_FILTER_VSE:
            year_value = date.today().year
        exec_maximized(RocniPlanDialog(self, year=year_value))

    def generate_inspections(self) -> None:
        year_value = self.year_filter.currentData()
        if year_value == YEAR_FILTER_VSE:
            year_value = date.today().year
        dialog = GenerateInspectionsDialog(self, year=year_value)
        if dialog.exec():
            self.refresh()

    def open_knowledge_editor(self) -> None:
        exec_maximized(ProverkyKnowledgeEditorDialog(self))

    def show_annual_report(self) -> None:
        year_value = self.year_filter.currentData()
        if year_value == YEAR_FILTER_VSE:
            year_value = date.today().year
        exec_maximized(RocniZpravaDialog(self, year=year_value))
