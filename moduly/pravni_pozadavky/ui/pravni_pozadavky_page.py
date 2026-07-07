from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from moduly.pravni_pozadavky.ui.pravni_predpisy_tab import PravniPredpisyTab
from moduly.pravni_pozadavky.ui.pravni_pozadavky_requirements_tab import (
    PravniPozadavkyRequirementsTab,
)


class PravniPozadavkyPage(QWidget):
    """Hlavní stránka registru právních požadavků."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.requirements_tab = PravniPozadavkyRequirementsTab()
        self.documents_tab = PravniPredpisyTab()

        self.tabs.addTab(self.requirements_tab, "Požadavky")
        self.tabs.addTab(self.documents_tab, "Právní předpisy")
        layout.addWidget(self.tabs)
