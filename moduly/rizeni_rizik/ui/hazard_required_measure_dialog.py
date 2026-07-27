from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import HAZARD_REQUIRED_MEASURE_DIALOG_TITLE
from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
    find_identification_working_copy,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    HazardRequiredMeasureError,
    hazard_required_measure_service,
)


class HazardRequiredMeasureDialog(QDialog):
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
        self.required_measure = measure
        self.read_only = read_only

        self.setWindowTitle(HAZARD_REQUIRED_MEASURE_DIALOG_TITLE)
        self.resize(560, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(100)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Název *:", self.title_edit)
        form.addRow("Popis:", self.description)
        form.addRow("", self.active_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if measure is not None:
            title = ""
            if hasattr(measure, "display_title"):
                title = measure.display_title()
            else:
                title = (getattr(measure, "title", None) or measure.description or "").strip()
            description = ""
            if hasattr(measure, "display_description"):
                description = measure.display_description()
            else:
                description = (getattr(measure, "note", None) or "").strip()
                stored_description = (getattr(measure, "description", None) or "").strip()
                if getattr(measure, "title", None) and stored_description != title:
                    description = stored_description or description
            self.title_edit.setText(title)
            self.description.setPlainText(description)
            self.active_checkbox.setChecked(bool(measure.active))

        if read_only:
            self.title_edit.setReadOnly(True)
            self.description.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        data = self.get_data()
        store = find_identification_working_copy(self)
        try:
            if store is not None:
                if self.required_measure is None:
                    store.create_required_measure(
                        hazard_risk_assessment_id=self.hazard_risk_assessment_id,
                        **data,
                    )
                else:
                    store.update_required_measure(
                        self.required_measure.id,
                        hazard_risk_assessment_id=self.hazard_risk_assessment_id,
                        **data,
                    )
            elif self.required_measure is None:
                hazard_required_measure_service.create_measure(
                    hazard_identification_id=self.hazard_identification_id,
                    hazard_risk_assessment_id=self.hazard_risk_assessment_id,
                    **data,
                )
            else:
                hazard_required_measure_service.update_measure(
                    self.required_measure.id,
                    hazard_identification_id=self.hazard_identification_id,
                    hazard_risk_assessment_id=self.hazard_risk_assessment_id,
                    **data,
                )
        except HazardRequiredMeasureError as error:
            QMessageBox.warning(self, HAZARD_REQUIRED_MEASURE_DIALOG_TITLE, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "description": self.description.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
