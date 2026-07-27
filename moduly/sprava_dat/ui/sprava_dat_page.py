from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from moduly.sprava_dat.ui.backup_tab import BackupTab
from moduly.sprava_dat.ui.codebooks_tab import CodebooksTab
from moduly.sprava_dat.ui.legal_registry_diagnostics_tab import LegalRegistryDiagnosticsTab
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
        self.backup_tab = BackupTab(on_status_changed=self.refresh_backup_status)
        self.transfer_tab = LegalRegistryTransferTab()
        self.codebooks_tab = CodebooksTab()
        self.diagnostics_tab = LegalRegistryDiagnosticsTab()

        self.tabs.addTab(self.summary_tab, TAB_SUMMARY)
        self.tabs.addTab(self.backup_tab, TAB_BACKUP)
        self.tabs.addTab(self.transfer_tab, TAB_TRANSFER)
        self.tabs.addTab(self.codebooks_tab, TAB_CODEBOOKS)
        self.tabs.addTab(self.diagnostics_tab, TAB_DIAGNOSTICS)
        layout.addWidget(self.tabs)

    def navigate_to_tab(self, tab_key: str) -> None:
        if tab_key not in TAB_ORDER:
            return
        self.tabs.setCurrentIndex(TAB_ORDER.index(tab_key))

    def refresh_backup_status(self) -> None:
        from moduly.sprava_dat.sluzby.data_management_settings_service import (
            data_management_settings_service,
        )

        data_management_settings_service.clear_stale_zip_last_backup()
        self.summary_tab.refresh()
        self.backup_tab.refresh()

    def refresh(self) -> None:
        self.tabs.setCurrentIndex(TAB_ORDER.index(TAB_SUMMARY))
        self.refresh_backup_status()
        self.transfer_tab.refresh()
        self.codebooks_tab.refresh()
        self.diagnostics_tab.refresh()
