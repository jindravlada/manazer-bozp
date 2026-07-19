from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.koordinace_bozp.constants import DIALOG_WINDOW_TITLE
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    BozpCoordinationError,
    bozp_coordination_service,
)
from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
from moduly.koordinace_bozp.ui.bozp_coordination_table import BozpCoordinationTable


class KoordinaceBozpPage(QWidget):
    """Úvodní stránka modulu – seznam koordinací (COORD-001)."""

    def __init__(self):
        super().__init__()

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

    def refresh(self) -> None:
        coordinations = bozp_coordination_service.get_all(include_inactive=True)
        self.table.load_coordinations(coordinations)
        configure_table_columns(self.table, "bozp_coordinations")
        self.table.clear_selection()
        self.text_filter.update_count()
        self._update_action_buttons()

    def new_coordination(self) -> None:
        dialog = BozpCoordinationDialog(self)
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
