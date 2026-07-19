from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.koordinace_bozp.constants import (
    DIALOG_WINDOW_TITLE,
    PBP_FILTER_ALL,
    PBP_FILTER_CURRENT,
    PBP_FILTER_LABELS,
    PBP_FILTER_MISSING,
    PBP_FILTER_NEEDS_UPDATE,
    PBP_FILTER_UNVERIFIABLE,
    VALIDITY_FILTER_ALL,
    VALIDITY_FILTER_EXPIRED,
    VALIDITY_FILTER_EXPIRING,
    VALIDITY_FILTER_LABELS,
    VALIDITY_FILTER_VALID,
)
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    BozpCoordinationError,
    bozp_coordination_service,
)
from moduly.koordinace_bozp.sluzby.coordination_pbp_freshness import PbpFreshnessCache
from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
from moduly.koordinace_bozp.ui.bozp_coordination_table import BozpCoordinationTable


class KoordinaceBozpPage(QWidget):
    """Úvodní stránka modulu – seznam koordinací."""

    def __init__(self):
        super().__init__()
        self._pbp_cache = PbpFreshnessCache()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nová koordinace")
        self.open_btn = QPushButton("Otevřít")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Platnost:"))
        self.validity_filter = QComboBox()
        for filter_id in (
            VALIDITY_FILTER_ALL,
            VALIDITY_FILTER_VALID,
            VALIDITY_FILTER_EXPIRING,
            VALIDITY_FILTER_EXPIRED,
        ):
            self.validity_filter.addItem(VALIDITY_FILTER_LABELS[filter_id], filter_id)
        toolbar.addWidget(self.validity_filter)

        toolbar.addWidget(QLabel("Příloha PBP:"))
        self.pbp_filter = QComboBox()
        for filter_id in (
            PBP_FILTER_ALL,
            PBP_FILTER_CURRENT,
            PBP_FILTER_NEEDS_UPDATE,
            PBP_FILTER_MISSING,
            PBP_FILTER_UNVERIFIABLE,
        ):
            self.pbp_filter.addItem(PBP_FILTER_LABELS[filter_id], filter_id)
        toolbar.addWidget(self.pbp_filter)

        self.table = BozpCoordinationTable()
        configure_table_columns(self.table, "bozp_coordinations")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat koordinaci...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_coordination)
        self.open_btn.clicked.connect(self.open_selected_coordination)
        self.activate_btn.clicked.connect(self.activate_selected_coordination)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_coordination)
        self.validity_filter.currentIndexChanged.connect(self.refresh)
        self.pbp_filter.currentIndexChanged.connect(self.refresh)
        self.table.doubleClicked.connect(self.open_selected_coordination)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.table.clear_selection()
        self._update_action_buttons()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def current_validity_filter(self) -> str:
        return self.validity_filter.currentData() or VALIDITY_FILTER_ALL

    def current_pbp_filter(self) -> str:
        return self.pbp_filter.currentData() or PBP_FILTER_ALL

    def refresh(self) -> None:
        self._pbp_cache.clear()
        coordinations = bozp_coordination_service.get_all(
            include_inactive=True,
            validity_filter=self.current_validity_filter(),
            pbp_filter=self.current_pbp_filter(),
            pbp_cache=self._pbp_cache,
        )
        self.table.load_coordinations(coordinations, pbp_cache=self._pbp_cache)
        configure_table_columns(self.table, "bozp_coordinations")
        self.table.clear_selection()
        self.text_filter.update_count()
        self._update_action_buttons()

    def new_coordination(self) -> None:
        dialog = BozpCoordinationDialog(self)
        dialog.showMaximized()
        if not dialog.exec():
            return
        try:
            bozp_coordination_service.create_coordination(**dialog.get_data())
        except BozpCoordinationError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            return
        self.refresh()

    def open_selected_coordination(self) -> None:
        coordination = self._selected_coordination()
        if coordination is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Vyberte koordinaci.")
            return
        dialog = BozpCoordinationDialog(self, coordination=coordination)
        dialog.showMaximized()
        if not dialog.exec():
            return
        try:
            bozp_coordination_service.update_coordination(
                coordination.id,
                **dialog.get_data(),
            )
        except BozpCoordinationError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            return
        self.refresh()

    def activate_selected_coordination(self) -> None:
        coordination = self._selected_coordination()
        if coordination is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Vyberte koordinaci.")
            return
        if coordination.active:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Koordinace je již aktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Aktivovat",
            f"Opravdu aktivovat koordinaci {coordination.coordination_number}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            bozp_coordination_service.activate(coordination.id)
            self.refresh()

    def deactivate_selected_coordination(self) -> None:
        coordination = self._selected_coordination()
        if coordination is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Vyberte koordinaci.")
            return
        if not coordination.active:
            QMessageBox.information(
                self,
                DIALOG_WINDOW_TITLE,
                "Koordinace je již neaktivní.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            f"Opravdu deaktivovat koordinaci {coordination.coordination_number}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            bozp_coordination_service.deactivate(coordination.id)
            self.refresh()

    def _selected_coordination(self):
        coordination_id = self.table.selected_coordination_id()
        if coordination_id is None:
            return None
        return bozp_coordination_service.get_by_id(coordination_id)

    def _update_action_buttons(self) -> None:
        coordination = self._selected_coordination()
        has_selection = coordination is not None
        self.open_btn.setEnabled(has_selection)
        if not has_selection:
            self.activate_btn.setEnabled(False)
            self.deactivate_btn.setEnabled(False)
            return
        self.activate_btn.setEnabled(not coordination.active)
        self.deactivate_btn.setEnabled(coordination.active)
