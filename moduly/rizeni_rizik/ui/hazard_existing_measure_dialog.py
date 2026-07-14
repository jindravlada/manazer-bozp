from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import HAZARD_EXISTING_MEASURE_DIALOG_TITLE
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    HazardExistingMeasureError,
    hazard_existing_measure_service,
)


class HazardExistingMeasureDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        hazard_identification_id: int,
        hazard_risk_assessment_id: int,
        measure=None,
        read_only: bool = False,
    ):
        super().__init__(parent)

        self.hazard_identification_id = hazard_identification_id
        self.hazard_risk_assessment_id = hazard_risk_assessment_id
        self.existing_measure = measure
        self.read_only = read_only

        self.setWindowTitle(HAZARD_EXISTING_MEASURE_DIALOG_TITLE)
        self.resize(560, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(100)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(60)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Popis opatření *:", self.description)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if measure is not None:
            self.description.setPlainText(measure.description)
            self.note.setPlainText(measure.note or "")
            self.active_checkbox.setChecked(bool(measure.active))

        if read_only:
            self.description.setReadOnly(True)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        data = self.get_data()
        try:
            if self.existing_measure is None:
                hazard_existing_measure_service.create_measure(
                    hazard_identification_id=self.hazard_identification_id,
                    hazard_risk_assessment_id=self.hazard_risk_assessment_id,
                    **data,
                )
            else:
                hazard_existing_measure_service.update_measure(
                    self.existing_measure.id,
                    hazard_identification_id=self.hazard_identification_id,
                    hazard_risk_assessment_id=self.hazard_risk_assessment_id,
                    **data,
                )
        except HazardExistingMeasureError as error:
            QMessageBox.warning(self, HAZARD_EXISTING_MEASURE_DIALOG_TITLE, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "description": self.description.toPlainText().strip(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
