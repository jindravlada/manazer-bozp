from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.rizeni_rizik.constants import (
    DIALOG_WINDOW_TITLE,
    RISK_IDENTIFICATION_DEFAULT_ACTIVE_FILTER,
    RISK_LIST_FILTER_ACTIVE,
    RISK_LIST_FILTER_ALL,
    RISK_LIST_FILTER_INACTIVE,
    RISK_MEASURE_REVIEW_TAB_TITLE,
)
from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_PAGE_TITLE
from moduly.rizeni_rizik.sluzby.hazard_identification_service import hazard_identification_service
from moduly.rizeni_rizik.ui.hazard_identification_dialog import HazardIdentificationDialog
from moduly.rizeni_rizik.ui.hazard_identification_table import HazardIdentificationTable
from moduly.rizeni_rizik.ui.hazard_library_page import HazardLibraryPage
from moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog import PravidlaBezpecnePraceDialog
from moduly.rizeni_rizik.ui.risk_measure_reviews_tab import RiskMeasureReviewsTab


class HazardIdentificationsTab(QWidget):
    def __init__(self, parent=None, on_open_library_template=None):
        super().__init__(parent)
        self._on_open_library_template = on_open_library_template

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nová identifikace")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        self.pravidla_btn = QPushButton("Pravidla bezpečné práce")
        self.edit_btn.setEnabled(False)
        self.activate_btn.setEnabled(False)
        self.deactivate_btn.setEnabled(False)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addWidget(self.pravidla_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Aktivní:"))
        self.active_filter = QComboBox()
        self.active_filter.addItem(RISK_LIST_FILTER_ACTIVE, RISK_LIST_FILTER_ACTIVE)
        self.active_filter.addItem(RISK_LIST_FILTER_INACTIVE, RISK_LIST_FILTER_INACTIVE)
        self.active_filter.addItem(RISK_LIST_FILTER_ALL, RISK_LIST_FILTER_ALL)
        default_index = self.active_filter.findData(RISK_IDENTIFICATION_DEFAULT_ACTIVE_FILTER)
        if default_index >= 0:
            self.active_filter.setCurrentIndex(default_index)
        self.active_filter.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(self.active_filter)

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
        self.pravidla_btn.clicked.connect(self.open_pravidla_bezpecne_prace)
        self.table.doubleClicked.connect(self.edit_selected_identification)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self.refresh()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _refresh_action_buttons(self, *_args) -> None:
        identification = self._selected_identification()
        single = identification is not None
        self.edit_btn.setEnabled(single)
        self.activate_btn.setEnabled(single and not identification.active)
        self.deactivate_btn.setEnabled(single and identification.active)

    def _show_table_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()

        identification = self._selected_identification()
        single = identification is not None
        if not single and not index.isValid():
            return

        menu = QMenu(self)
        edit_action = menu.addAction("Upravit", self.edit_selected_identification)
        edit_action.setEnabled(single)
        activate_action = menu.addAction("Aktivovat", self.activate_selected_identification)
        activate_action.setEnabled(single and identification is not None and not identification.active)
        deactivate_action = menu.addAction("Deaktivovat", self.deactivate_selected_identification)
        deactivate_action.setEnabled(single and identification is not None and identification.active)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def new_identification(self) -> None:
        dialog = HazardIdentificationDialog(
            self,
            on_open_library_template=self._on_open_library_template,
        )
        exec_maximized(dialog)
        self.refresh()

    def open_pravidla_bezpecne_prace(self) -> None:
        dialog = PravidlaBezpecnePraceDialog(self)
        dialog.exec()

    def edit_selected_identification(self) -> None:
        identification = self._selected_identification()
        if identification is None:
            return

        dialog = HazardIdentificationDialog(
            self,
            identification=identification,
            on_open_library_template=self._on_open_library_template,
        )
        exec_maximized(dialog)
        self.refresh()

    def activate_selected_identification(self) -> None:
        identification = self._selected_identification()
        if identification is None:
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
        if self._selected_row_count() != 1:
            return None
        identification_id = self.table.selected_identification_id()
        if identification_id is None:
            return None
        return hazard_identification_service.get_by_id(identification_id)

    def refresh(self) -> None:
        mode = self.active_filter.currentData()
        identifications = hazard_identification_service.get_all(include_inactive=True)
        if mode == RISK_LIST_FILTER_ACTIVE:
            identifications = [item for item in identifications if item.active]
        elif mode == RISK_LIST_FILTER_INACTIVE:
            identifications = [item for item in identifications if not item.active]
        self.table.load_identifications(identifications)
        configure_table_columns(self.table, "hazard_identifications")
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.text_filter.update_count()
        self._refresh_action_buttons()


class RizeniRizikPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.library_tab_index = 1
        self.identifications_tab = HazardIdentificationsTab(
            on_open_library_template=self.open_library_template,
        )
        self.library_page = HazardLibraryPage()
        self.reviews_tab = RiskMeasureReviewsTab()
        self.tabs.addTab(self.identifications_tab, "Identifikace")
        self.tabs.addTab(self.library_page, HAZARD_LIBRARY_PAGE_TITLE)
        self.tabs.addTab(self.reviews_tab, RISK_MEASURE_REVIEW_TAB_TITLE)
        layout.addWidget(self.tabs)

    def open_library_template(self, template_id: int) -> None:
        self.tabs.setCurrentIndex(self.library_tab_index)
        self.library_page.open_template(template_id)

    def open_library_template_editor(self, template_id: int) -> None:
        self.tabs.setCurrentIndex(self.library_tab_index)
        self.library_page.open_template_editor(template_id)

    def refresh(self) -> None:
        self.identifications_tab.refresh()
        self.library_page.refresh()
        self.reviews_tab.refresh()
