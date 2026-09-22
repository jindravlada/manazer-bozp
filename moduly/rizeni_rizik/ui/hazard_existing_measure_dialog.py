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
from moduly.rizeni_rizik.constants import (
    EXISTING_MEASURE_RELEVANCE_LABEL,
    HAZARD_EXISTING_MEASURE_DIALOG_TITLE,
)
from moduly.rizeni_rizik.sluzby.existing_measure_relevance import (
    EXISTING_MEASURE_RELEVANCE_REQUIRED,
)
from moduly.rizeni_rizik.sluzby.exposed_target_ref import ExposedTargetRef
from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
    find_identification_working_copy,
)
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    HazardExistingMeasureError,
    hazard_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    hazard_risk_assessment_service,
)
from moduly.rizeni_rizik.ui.existing_measure_relevance_selector import (
    ExistingMeasureRelevanceSelector,
    add_active_checkbox_separated as _add_active_checkbox_separated,
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
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(100)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(60)
        self.relevance = ExistingMeasureRelevanceSelector(self)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Popis opatření *:", self.description)
        form.addRow("Poznámka:", self.note)
        form.addRow(f"{EXISTING_MEASURE_RELEVANCE_LABEL}:", self.relevance)
        _add_active_checkbox_separated(form, self.active_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        available = self._assessment_refs()
        if measure is not None:
            self.description.setPlainText(measure.description)
            self.note.setPlainText(measure.note or "")
            self.active_checkbox.setChecked(bool(measure.active))
            self.relevance.set_options(available, self._measure_refs(measure))
        else:
            self.relevance.set_options(available)

        if read_only:
            self.description.setReadOnly(True)
            self.note.setReadOnly(True)
            self.relevance.setEnabled(False)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _assessment_refs(self) -> list[ExposedTargetRef]:
        store = find_identification_working_copy(self)
        if store is not None:
            assessment = store.get_assessment(self.hazard_risk_assessment_id)
            if assessment is not None:
                return list(assessment.target_refs)
        return hazard_risk_assessment_service.get_target_refs(
            self.hazard_risk_assessment_id,
        )

    def _measure_refs(self, measure) -> list[ExposedTargetRef]:
        stored = getattr(measure, "target_refs", None)
        if stored is not None:
            return list(stored)
        return hazard_existing_measure_service.get_target_refs(measure.id)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        data = self.get_data()
        if self.relevance.available_refs() and not data["target_refs"]:
            QMessageBox.warning(
                self,
                HAZARD_EXISTING_MEASURE_DIALOG_TITLE,
                EXISTING_MEASURE_RELEVANCE_REQUIRED,
            )
            return

        store = find_identification_working_copy(self)
        try:
            if store is not None:
                if self.existing_measure is None:
                    store.create_existing_measure(
                        hazard_risk_assessment_id=self.hazard_risk_assessment_id,
                        **data,
                    )
                else:
                    store.update_existing_measure(
                        self.existing_measure.id,
                        hazard_risk_assessment_id=self.hazard_risk_assessment_id,
                        **data,
                    )
            elif self.existing_measure is None:
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
            "target_refs": self.relevance.selected_refs(),
        }
