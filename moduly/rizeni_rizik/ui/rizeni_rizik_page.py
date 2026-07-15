from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.rizeni_rizik.constants import DIALOG_WINDOW_TITLE
from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_PAGE_TITLE
from moduly.rizeni_rizik.sluzby.hazard_identification_service import hazard_identification_service
from moduly.rizeni_rizik.ui.hazard_identification_dialog import HazardIdentificationDialog
from moduly.rizeni_rizik.ui.hazard_identification_table import HazardIdentificationTable
from moduly.rizeni_rizik.ui.hazard_library_page import HazardLibraryPage


class HazardIdentificationsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nová identifikace")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()

        self.table = HazardIdentificationTable()
        configure_table_columns(self.table, "hazard_identifications")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat identifikaci...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_identification)
        self.edit_btn.clicked.connect(self.edit_selected_identification)
        self.activate_btn.clicked.connect(self.activate_selected_identification)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_identification)
        self.table.doubleClicked.connect(self.edit_selected_identification)

        self.refresh()

    def new_identification(self) -> None:
        dialog = HazardIdentificationDialog(self)
        exec_maximized(dialog)
        self.refresh()

    def edit_selected_identification(self) -> None:
        identification_id = self.table.selected_identification_id()
        if identification_id is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Vyberte identifikaci.")
            return

        identification = hazard_identification_service.get_by_id(identification_id)
        if identification is None:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, "Identifikace nebyla nalezena.")
            self.refresh()
            return

        dialog = HazardIdentificationDialog(self, identification=identification)
        exec_maximized(dialog)
        self.refresh()

    def activate_selected_identification(self) -> None:
        identification = self._selected_identification()
        if identification is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Vyberte identifikaci.")
            return
        if identification.active:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Identifikace je již aktivní.")
            return

        answer = QMessageBox.question(
            self,
            "Aktivovat",
            f"Opravdu aktivovat identifikaci {identification.identification_number}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            hazard_identification_service.activate(identification.id)
            self.refresh()

    def deactivate_selected_identification(self) -> None:
        identification = self._selected_identification()
        if identification is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Vyberte identifikaci.")
            return
        if not identification.active:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Identifikace je již neaktivní.")
            return

        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            f"Opravdu deaktivovat identifikaci {identification.identification_number}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            hazard_identification_service.deactivate(identification.id)
            self.refresh()

    def _selected_identification(self):
        identification_id = self.table.selected_identification_id()
        if identification_id is None:
            return None
        return hazard_identification_service.get_by_id(identification_id)

    def refresh(self) -> None:
        identifications = hazard_identification_service.get_all(include_inactive=True)
        self.table.load_identifications(identifications)
        configure_table_columns(self.table, "hazard_identifications")
        self.text_filter.update_count()


class RizeniRizikPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.identifications_tab = HazardIdentificationsTab()
        self.library_page = HazardLibraryPage()
        self.tabs.addTab(self.identifications_tab, "Identifikace")
        self.tabs.addTab(self.library_page, HAZARD_LIBRARY_PAGE_TITLE)
        layout.addWidget(self.tabs)

    def refresh(self) -> None:
        self.identifications_tab.refresh()
        self.library_page.refresh()
