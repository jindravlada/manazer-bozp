from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from moduly.pravni_pozadavky.ui.pravni_predpisy_tab import PravniPredpisyTab
from moduly.pravni_pozadavky.ui.pravni_pozadavky_requirements_tab import (
    PravniPozadavkyRequirementsTab,
)
from moduly.pravni_pozadavky.ui.zmeny_legislativy_tab import ZmenyLegislativyTab


class PravniPozadavkyPage(QWidget):
    """Hlavní stránka registru právních požadavků."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.requirements_tab = PravniPozadavkyRequirementsTab()
        self.documents_tab = PravniPredpisyTab()
        self.changes_tab = ZmenyLegislativyTab()

        self.tabs.addTab(self.requirements_tab, "Požadavky")
        self.tabs.addTab(self.documents_tab, "Právní předpisy")
        self.tabs.addTab(self.changes_tab, "Změny legislativy")
        layout.addWidget(self.tabs)
