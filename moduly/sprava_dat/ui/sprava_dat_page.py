from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from moduly.sprava_dat.ui.backup_tab import BackupTab
from moduly.sprava_dat.ui.legal_registry_transfer_tab import LegalRegistryTransferTab
from moduly.sprava_dat.ui.summary_tab import SummaryTab
from moduly.sprava_dat.ui.tab_constants import (
    TAB_BACKUP,
    TAB_CODEBOOKS,
    TAB_DIAGNOSTICS,
    TAB_ORDER,
    TAB_SUMMARY,
    TAB_TRANSFER,
)


class SpravaDatPage(QWidget):
    """Servisní stránka pro správu dat aplikace."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Správa dat")
        title_font = QFont(title.font())
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.summary_tab = SummaryTab(navigate_callback=self.navigate_to_tab)
        self.backup_tab = BackupTab()
        self.transfer_tab = LegalRegistryTransferTab()

        self.tabs.addTab(self.summary_tab, TAB_SUMMARY)
        self.tabs.addTab(self.backup_tab, TAB_BACKUP)
        self.tabs.addTab(self.transfer_tab, TAB_TRANSFER)
        self.tabs.addTab(self._codebooks_tab(), TAB_CODEBOOKS)
        self.tabs.addTab(self._diagnostics_tab(), TAB_DIAGNOSTICS)
        layout.addWidget(self.tabs)

    def _codebooks_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(12, 12, 12, 12)
        tab_layout.addWidget(QLabel("• Číselníky"))
        tab_layout.addStretch()
        return tab

    def _diagnostics_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(12, 12, 12, 12)
        tab_layout.addWidget(QLabel("Diagnostika registru právních požadavků"))
        tab_layout.addStretch()
        return tab

    def navigate_to_tab(self, tab_key: str) -> None:
        if tab_key not in TAB_ORDER:
            return
        self.tabs.setCurrentIndex(TAB_ORDER.index(tab_key))

    def refresh(self) -> None:
        self.tabs.setCurrentIndex(TAB_ORDER.index(TAB_SUMMARY))
        self.summary_tab.refresh()
        self.backup_tab.refresh()
        self.transfer_tab.refresh()
