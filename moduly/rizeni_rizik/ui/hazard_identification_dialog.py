from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QTabWidget, QVBoxLayout, QWidget

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import (
    DIALOG_WINDOW_TITLE,
    HAZARD_IDENTIFICATION_TABS,
    TAB_BASICS,
    TAB_INVENTORY,
    is_identification_inventory_read_only,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    HazardIdentificationError,
    hazard_identification_service,
)
from moduly.rizeni_rizik.ui.hazard_identification_basics_widget import (
    HazardIdentificationBasicsWidget,
)
from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget


class HazardIdentificationDialog(QDialog):
    def __init__(self, parent=None, identification=None):
        super().__init__(parent)

        self.identification = identification

        self.setWindowTitle(DIALOG_WINDOW_TITLE)
        self.resize(960, 680)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.basics_widget = HazardIdentificationBasicsWidget()
        self.inventory_widget = HazardInventoryWidget()
        self.tabs.addTab(self.basics_widget, TAB_BASICS)
        self.tabs.addTab(self.inventory_widget, TAB_INVENTORY)

        for tab_label in HAZARD_IDENTIFICATION_TABS[2:]:
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout(placeholder)
            placeholder_layout.addWidget(QLabel("Obsah bude doplněn v další fázi."))
            placeholder_layout.addStretch()
            index = self.tabs.addTab(placeholder, tab_label)
            self.tabs.setTabEnabled(index, False)

        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.clicked.connect(self._save_basics)
        if cancel_button is not None:
            cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self.basics_widget.load_identification(identification)
        self._sync_inventory_context()
        self._update_inventory_tab_enabled()

    def _update_inventory_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(1, self.identification is not None)

    def _sync_inventory_context(self) -> None:
        identification_id = self.identification.id if self.identification is not None else None
        status = self.identification.status if self.identification is not None else ""
        self.inventory_widget.set_identification(
            identification_id,
            read_only=is_identification_inventory_read_only(status),
        )

    def _save_basics(self) -> None:
        data = self.basics_widget.get_data()
        try:
            if self.identification is None:
                self.identification = hazard_identification_service.create_identification(**data)
            else:
                updated = hazard_identification_service.update_identification(
                    self.identification.id,
                    **data,
                )
                if updated is not None:
                    self.identification = updated
        except HazardIdentificationError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            self.tabs.setCurrentWidget(self.basics_widget)
            return

        self._update_inventory_tab_enabled()
        self._sync_inventory_context()
        QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Základní údaje byly uloženy.")

    def get_data(self) -> dict:
        return self.basics_widget.get_data()
