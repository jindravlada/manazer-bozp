from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.proverky.constants import TAB_KONTROLOVANE_OBLASTI
from moduly.proverky.ui.bozp_inspection_areas_widget import BozpInspectionAreasWidget
from moduly.proverky.ui.bozp_inspection_spis_widget import BozpInspectionSpisWidget


class BozpInspectionDialog(QDialog):
    """Dialog prověrky BOZP — bez ukládání a business logiky."""

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
        self.tabs.addTab(self._placeholder_tab("Zjištění"), "Zjištění")
        self.tabs.addTab(self._placeholder_tab("Úkoly"), "Úkoly")
        self.tabs.addTab(self._placeholder_tab("Přílohy"), "Přílohy")
        self.tabs.addTab(self._placeholder_tab("Závěr"), "Závěr")
        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.spis_widget.load_inspection(inspection)

    def _placeholder_tab(self, title: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            f"Záložka „{title}“ bude doplněna v další fázi vývoje.\n"
            "Modul zatím pracuje pouze jako kostra bez ukládání dat."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()
        return tab
