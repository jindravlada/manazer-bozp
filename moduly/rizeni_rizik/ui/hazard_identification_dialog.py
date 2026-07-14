from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QTabWidget, QVBoxLayout, QWidget

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import (
    DIALOG_WINDOW_TITLE,
    HAZARD_IDENTIFICATION_TABS,
    TAB_BASICS,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    HazardIdentificationError,
    hazard_identification_service,
)
from moduly.rizeni_rizik.ui.hazard_identification_basics_widget import (
    HazardIdentificationBasicsWidget,
)


class HazardIdentificationDialog(QDialog):
    def __init__(self, parent=None, identification=None):
        super().__init__(parent)

        self.identification = identification

        self.setWindowTitle(DIALOG_WINDOW_TITLE)
        self.resize(760, 620)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.basics_widget = HazardIdentificationBasicsWidget()
        self.tabs.addTab(self.basics_widget, TAB_BASICS)

        for tab_label in HAZARD_IDENTIFICATION_TABS[1:]:
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout(placeholder)
            placeholder_layout.addWidget(QLabel("Obsah bude doplněn v další fázi."))
            placeholder_layout.addStretch()
            index = self.tabs.addTab(placeholder, tab_label)
            self.tabs.setTabEnabled(index, False)

        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.basics_widget.load_identification(identification)

    def accept(self) -> None:
        data = self.basics_widget.get_data()
        try:
            if self.identification is None:
                hazard_identification_service.create_identification(**data)
            else:
                hazard_identification_service.update_identification(
                    self.identification.id,
                    **data,
                )
        except HazardIdentificationError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            self.tabs.setCurrentWidget(self.basics_widget)
            return
        super().accept()

    def get_data(self) -> dict:
        return self.basics_widget.get_data()
