from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from moduly.pravni_pozadavky.constants import legal_requirement_process_label

ATTACH_MODE = "attach"
CREATE_MODE = "create"


class LegalRequirementSectionAttachDialog(QDialog):
    def __init__(self, parent=None, *, processes: list | None = None):
        super().__init__(parent)
        self._processes = list(processes or [])
        self._selected_mode = ATTACH_MODE
        self._selected_requirement_id: int | None = None

        self.setWindowTitle("Přiřazení ustanovení")
        configure_resizable_form_dialog(self, width=560, height=220, min_width=460, min_height=200)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Toto ustanovení zatím není přiřazeno."))
        layout.addWidget(QLabel("Co chcete udělat?"))

        self.attach_radio = QRadioButton("Připojit k existujícímu procesu")
        self.create_radio = QRadioButton("Vytvořit nový proces")
        self.attach_radio.setChecked(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.attach_radio)
        self.mode_group.addButton(self.create_radio)

        self.process_combo = QComboBox()
        for requirement in self._processes:
            label = legal_requirement_process_label(requirement)
            if not label:
                label = f"Proces #{requirement.id}"
            self.process_combo.addItem(label, requirement.id)

        layout.addWidget(self.attach_radio)
        layout.addWidget(self.process_combo)
        layout.addWidget(self.create_radio)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.attach_radio.toggled.connect(self._update_controls)
        self._update_controls()

    def create_new_process(self) -> bool:
        return self._selected_mode == CREATE_MODE

    def selected_requirement_id(self) -> int | None:
        return self._selected_requirement_id

    def _update_controls(self) -> None:
        attach_selected = self.attach_radio.isChecked()
        self.process_combo.setEnabled(attach_selected and bool(self._processes))

    def _accept(self) -> None:
        if self.attach_radio.isChecked():
            requirement_id = self.process_combo.currentData()
            if requirement_id is None:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(self, "Přiřazení ustanovení", "Vyberte existující proces.")
                return
            self._selected_mode = ATTACH_MODE
            self._selected_requirement_id = requirement_id
        else:
            self._selected_mode = CREATE_MODE
            self._selected_requirement_id = None
        self.accept()
