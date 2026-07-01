from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.proverky.constants import TAB_KONTROLOVANE_OBLASTI
from moduly.proverky.sluzby.bozp_inspection_commission_service import (
    bozp_inspection_commission_service,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.proverky.ui.bozp_inspection_areas_widget import BozpInspectionAreasWidget
from moduly.proverky.ui.bozp_inspection_commission_widget import BozpInspectionCommissionWidget
from moduly.proverky.ui.bozp_inspection_conclusion_widget import BozpInspectionConclusionWidget
from moduly.proverky.ui.bozp_inspection_findings_widget import BozpInspectionFindingsWidget
from moduly.proverky.ui.bozp_inspection_spis_widget import BozpInspectionSpisWidget
from moduly.proverky.ui.bozp_inspection_tasks_widget import BozpInspectionTasksWidget


class BozpInspectionDialog(QDialog):
    """Dialog prověrky BOZP."""

    def __init__(self, parent=None, inspection=None):
        super().__init__(parent)

        self.inspection = inspection

        self.setWindowTitle("Prověrka BOZP")
        self.resize(860, 720)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.spis_widget = BozpInspectionSpisWidget()
        self.commission_widget = BozpInspectionCommissionWidget()
        self.tabs.addTab(self.spis_widget, "Spis")
        self.tabs.addTab(self.commission_widget, "Komise")
        self.areas_widget = BozpInspectionAreasWidget()
        self.tabs.addTab(self.areas_widget, TAB_KONTROLOVANE_OBLASTI)
        self.findings_widget = BozpInspectionFindingsWidget()
        self.tabs.addTab(self.findings_widget, "Zjištění")
        self.tasks_widget = BozpInspectionTasksWidget()
        self.tabs.addTab(self.tasks_widget, "Úkoly")
        self.tabs.addTab(self._placeholder_tab("Přílohy"), "Přílohy")
        self.conclusion_widget = BozpInspectionConclusionWidget()
        self.tabs.addTab(self.conclusion_widget, "Závěr")
        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        inspection_id = inspection.id if inspection is not None else None
        self.set_inspection_id(inspection_id)
        self.areas_widget.set_on_finding_saved(self._on_finding_changed)
        self.findings_widget.set_on_task_changed(self._on_related_data_changed)
        self.conclusion_widget.set_complete_handler(self._complete_inspection)
        self.spis_widget.load_inspection(inspection)
        self.conclusion_widget.load_inspection(inspection)
        self.commission_widget.set_inspection_context(inspection_id)

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self.areas_widget.set_inspection_id(inspection_id)
        self.findings_widget.set_inspection_id(inspection_id)
        self.tasks_widget.set_inspection_id(inspection_id)

    def _on_finding_changed(self) -> None:
        self._on_related_data_changed()
        self.areas_widget.refresh_findings_display()

    def _on_related_data_changed(self) -> None:
        self.findings_widget.refresh()
        self.tasks_widget.refresh()
        self.conclusion_widget.refresh()

    def accept(self) -> None:
        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Komise", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return
        super().accept()

    def get_data(self) -> dict:
        data = self.spis_widget.get_data()
        data.update(self.conclusion_widget.get_data())
        data["title"] = ""
        data["commission_members"] = self.commission_widget.get_members_for_save()
        return data

    def _prepare_save_payload(self, data: dict) -> dict:
        payload = {key: value for key, value in data.items() if key != "commission_members"}

        workplace_id = payload.get("workplace_id")
        if workplace_id is None:
            workplace_id = bozp_inspection_service.resolve_workplace_id_by_name(
                payload.get("workplace_name", "")
            )
            payload["workplace_id"] = workplace_id
        payload["workplace_name"] = bozp_inspection_service.resolve_workplace_name(workplace_id)
        payload["title"] = ""
        return payload

    def _complete_inspection(self, *, status: str, finished_at) -> bool:
        if self.inspection is None:
            return False

        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Komise", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return False

        data = self.get_data()
        data["status"] = status
        data["finished_at"] = finished_at
        payload = self._prepare_save_payload(data)

        updated = bozp_inspection_service.update_inspection(self.inspection.id, **payload)
        if updated is None:
            return False

        bozp_inspection_commission_service.save_members(
            self.inspection.id,
            data.get("commission_members", []),
        )

        self.inspection = updated
        self.conclusion_widget.load_inspection(self.inspection)
        return True

    def _placeholder_tab(self, title: str):
        from PySide6.QtWidgets import QLabel, QWidget

        tab = QWidget()
        tab_layout = QVBoxLayout(tab)

        info = QLabel(
            f"Záložka „{title}“ bude doplněna v další fázi vývoje."
        )
        info.setWordWrap(True)
        tab_layout.addWidget(info)
        tab_layout.addStretch()
        return tab
