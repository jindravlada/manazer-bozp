from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from moduly.sprava_dat.ui.backup_tab import BackupTab
from moduly.sprava_dat.ui.legal_registry_transfer_tab import LegalRegistryTransferTab

TAB_BACKUP = "Zálohování"
TAB_TRANSFER = "Přenos dat"
TAB_CODEBOOKS = "Číselníky"
TAB_DIAGNOSTICS = "Diagnostika"


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
        self.backup_tab = BackupTab()
        self.tabs.addTab(self.backup_tab, TAB_BACKUP)
        self.transfer_tab = LegalRegistryTransferTab()
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

    def refresh(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.backup_tab.refresh()
        self.transfer_tab.refresh()
