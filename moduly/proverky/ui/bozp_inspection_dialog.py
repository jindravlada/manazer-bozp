from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.proverky.constants import TAB_KONTROLOVANE_OBLASTI
from moduly.proverky.ui.bozp_inspection_areas_widget import BozpInspectionAreasWidget
from moduly.proverky.ui.bozp_inspection_commission_widget import BozpInspectionCommissionWidget
from moduly.proverky.ui.bozp_inspection_findings_widget import BozpInspectionFindingsWidget
from moduly.proverky.ui.bozp_inspection_spis_widget import BozpInspectionSpisWidget


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
        self.tabs.addTab(self._placeholder_tab("Úkoly"), "Úkoly")
        self.tabs.addTab(self._placeholder_tab("Přílohy"), "Přílohy")
        self.tabs.addTab(self._placeholder_tab("Závěr"), "Závěr")
        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        inspection_id = inspection.id if inspection is not None else None
        team_id = getattr(inspection, "team_id", None) if inspection is not None else None
        self.set_inspection_id(inspection_id)
        self.areas_widget.set_on_finding_saved(self._on_finding_changed)
        self.spis_widget.load_inspection(inspection)
        self.commission_widget.set_inspection_context(inspection_id, team_id)

        self.spis_widget.team_selection_changed.connect(self._on_team_selection_changed)

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self.areas_widget.set_inspection_id(inspection_id)
        self.findings_widget.set_inspection_id(inspection_id)

    def _on_finding_changed(self) -> None:
        self.findings_widget.refresh()
        self.areas_widget.refresh_findings_display()

    def _on_team_selection_changed(self, new_team_id, old_team_id) -> None:
        commission = self.commission_widget

        if new_team_id is None:
            commission.current_team_id = None
            if commission.has_template_members():
                commission.load_from_team(None, keep_ad_hoc=True)
            commission._update_buttons()
            return

        if not commission.has_members():
            commission.load_from_team(new_team_id)
            return

        if old_team_id is not None and old_team_id != new_team_id:
            answer = QMessageBox.question(
                self,
                "Načíst novou komisi",
                "Změnili jste prověrkovou komisi. Načíst členy z nové šablony?\n\n"
                "Přizvané osoby přidané jen k této prověrce zůstanou zachovány.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                commission.load_from_team(new_team_id, keep_ad_hoc=True)
            else:
                commission.current_team_id = new_team_id
                commission._update_buttons()
            return

        commission.load_from_team(new_team_id)

    def get_data(self) -> dict:
        data = self.spis_widget.get_data()
        data["title"] = ""
        data["commission_members"] = self.commission_widget.get_members_for_save()
        return data

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
