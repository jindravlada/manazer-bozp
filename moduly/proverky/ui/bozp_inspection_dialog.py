from PySide6.QtWidgets import (
    QDialog,
    QTabWidget,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.proverky.constants import TAB_KONTROLOVANE_OBLASTI
from moduly.proverky.ui.bozp_inspection_areas_widget import BozpInspectionAreasWidget
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
        self.tabs.addTab(self.spis_widget, "Spis")
        self.tabs.addTab(self._placeholder_tab("Komise"), "Komise")
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
        self.set_inspection_id(inspection_id)
        self.areas_widget.set_on_finding_saved(self._on_finding_changed)
        self.spis_widget.load_inspection(inspection)

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self.areas_widget.set_inspection_id(inspection_id)
        self.findings_widget.set_inspection_id(inspection_id)

    def _on_finding_changed(self) -> None:
        self.findings_widget.refresh()
        self.areas_widget.refresh_findings_display()

    def get_data(self) -> dict:
        data = self.spis_widget.get_data()
        data["title"] = ""
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
