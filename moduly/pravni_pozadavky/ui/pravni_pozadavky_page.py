from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from moduly.pravni_pozadavky.ui.kontroly_legislativy_tab import KontrolyLegislativyTab
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
        self.check_runs_tab = KontrolyLegislativyTab()

        self.tabs.addTab(self.requirements_tab, "Řídicí procesy")
        self.tabs.addTab(self.documents_tab, "Právní předpisy")
        self.tabs.addTab(self.check_runs_tab, "Kontroly změn")
        self.tabs.addTab(self.changes_tab, "Zjištěné změny")
        layout.addWidget(self.tabs)

    def on_requirement_created(self, requirement_id: int | None = None) -> None:
        self.tabs.setCurrentWidget(self.requirements_tab)
        self.requirements_tab.show_created_requirement(requirement_id)
