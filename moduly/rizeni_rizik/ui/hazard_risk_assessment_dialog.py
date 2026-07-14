from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import HAZARD_RISK_ASSESSMENT_DIALOG_TITLE
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    HazardRiskAssessmentError,
    hazard_risk_assessment_service,
)


class HazardRiskAssessmentDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        hazard_identification_id: int,
        assessment=None,
        default_hazard_event_id: int | None = None,
        read_only: bool = False,
    ):
        super().__init__(parent)

        self.hazard_identification_id = hazard_identification_id
        self.risk_assessment = assessment
        self.read_only = read_only

        self.setWindowTitle(HAZARD_RISK_ASSESSMENT_DIALOG_TITLE)
        self.resize(560, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.event = QComboBox()
        self._populate_events(default_hazard_event_id)

        self.exposed_group = QLineEdit()
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(80)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Nežádoucí událost *:", self.event)
        form.addRow("Ohrožená skupina *:", self.exposed_group)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if assessment is not None:
            index = self.event.findData(assessment.hazard_event_id)
            if index >= 0:
                self.event.setCurrentIndex(index)
            self.exposed_group.setText(assessment.exposed_group)
            self.note.setPlainText(assessment.note or "")
            self.active_checkbox.setChecked(bool(assessment.active))

        if read_only:
            self.event.setEnabled(False)
            self.exposed_group.setReadOnly(True)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _populate_events(self, default_hazard_event_id: int | None) -> None:
        rows = hazard_risk_assessment_service.get_event_candidates(
            self.hazard_identification_id
        )
        self.event.clear()
        for row in rows:
            label = f"{row.event.name} ({row.hazard_name})"
            self.event.addItem(label, row.event.id)

        if default_hazard_event_id is not None:
            index = self.event.findData(default_hazard_event_id)
            if index >= 0:
                self.event.setCurrentIndex(index)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        data = self.get_data()
        try:
            if self.risk_assessment is None:
                hazard_risk_assessment_service.create_assessment(
                    hazard_identification_id=self.hazard_identification_id,
                    **data,
                )
            else:
                hazard_risk_assessment_service.update_assessment(
                    self.risk_assessment.id,
                    hazard_identification_id=self.hazard_identification_id,
                    **data,
                )
        except HazardRiskAssessmentError as error:
            QMessageBox.warning(self, HAZARD_RISK_ASSESSMENT_DIALOG_TITLE, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "hazard_event_id": self.event.currentData(),
            "exposed_group": self.exposed_group.text().strip(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
