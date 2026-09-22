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
from moduly.rizeni_rizik.constants import EXISTING_MEASURE_RELEVANCE_LABEL
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_EXISTING_MEASURE_DIALOG_TITLE,
    HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE,
)
from moduly.rizeni_rizik.sluzby.existing_measure_relevance import (
    EXISTING_MEASURE_RELEVANCE_REQUIRED,
)
from moduly.rizeni_rizik.sluzby.exposed_target_ref import ExposedTargetRef
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    HazardLibraryTemplateExistingMeasureError,
    hazard_library_template_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
    HazardLibraryTemplateRequiredMeasureError,
    hazard_library_template_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_working_copy import (
    find_catalog_working_copy,
)
from moduly.rizeni_rizik.ui.existing_measure_relevance_selector import (
    ExistingMeasureRelevanceSelector,
)


class HazardLibraryTemplateMeasureDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        template_id: int,
        template_assessment_id: int,
        measure=None,
        measure_type: str = "existing",
        read_only: bool = False,
    ):
        super().__init__(parent)

        self.template_id = template_id
        self.template_assessment_id = template_assessment_id
        self.measure = measure
        self.measure_type = measure_type
        self.read_only = read_only

        title = (
            HAZARD_LIBRARY_EXISTING_MEASURE_DIALOG_TITLE
            if measure_type == "existing"
            else HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE
        )
        self.setWindowTitle(title)
        self.resize(560, 420 if measure_type == "existing" else 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(100)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(60)
        self.relevance = None
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        description_label = (
            "Popis opatření *:"
            if measure_type == "existing"
            else "Kontrolní otázka *:"
        )
        form.addRow(description_label, self.description)
        form.addRow("Poznámka:", self.note)
        if measure_type == "existing":
            self.relevance = ExistingMeasureRelevanceSelector(self)
            form.addRow(f"{EXISTING_MEASURE_RELEVANCE_LABEL}:", self.relevance)
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

        if self.relevance is not None:
            available = self._assessment_refs()
            if measure is not None:
                self.relevance.set_options(available, self._measure_refs(measure))
            else:
                self.relevance.set_options(available)

        if read_only:
            self.description.setReadOnly(True)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            if self.relevance is not None:
                self.relevance.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _assessment_refs(self) -> list[ExposedTargetRef]:
        store = find_catalog_working_copy(self)
        if store is not None:
            assessment = store.get_assessment(self.template_assessment_id)
            if assessment is not None:
                return list(assessment.target_refs)
        return hazard_library_template_assessment_service.get_target_refs(
            self.template_assessment_id,
        )

    def _measure_refs(self, measure) -> list[ExposedTargetRef]:
        stored = getattr(measure, "target_refs", None)
        if stored is not None:
            return list(stored)
        return hazard_library_template_existing_measure_service.get_target_refs(measure.id)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        data = self.get_data()
        title = (
            HAZARD_LIBRARY_EXISTING_MEASURE_DIALOG_TITLE
            if self.measure_type == "existing"
            else HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE
        )
        if (
            self.relevance is not None
            and self.relevance.available_refs()
            and not data.get("target_refs")
        ):
            QMessageBox.warning(self, title, EXISTING_MEASURE_RELEVANCE_REQUIRED)
            return
        try:
            store = find_catalog_working_copy(self)
            if self.measure_type == "existing":
                if self.measure is None:
                    if store is not None:
                        store.create_existing_measure(
                            template_id=self.template_id,
                            template_assessment_id=self.template_assessment_id,
                            **data,
                        )
                    else:
                        hazard_library_template_existing_measure_service.create_measure(
                            template_id=self.template_id,
                            template_assessment_id=self.template_assessment_id,
                            **data,
                        )
                elif store is not None:
                    store.update_existing_measure(
                        self.measure.id,
                        template_id=self.template_id,
                        template_assessment_id=self.template_assessment_id,
                        **data,
                    )
                else:
                    hazard_library_template_existing_measure_service.update_measure(
                        self.measure.id,
                        template_id=self.template_id,
                        template_assessment_id=self.template_assessment_id,
                        **data,
                    )
            elif self.measure is None:
                if store is not None:
                    store.create_required_measure(
                        template_id=self.template_id,
                        template_assessment_id=self.template_assessment_id,
                        **data,
                    )
                else:
                    hazard_library_template_required_measure_service.create_measure(
                        template_id=self.template_id,
                        template_assessment_id=self.template_assessment_id,
                        **data,
                    )
            elif store is not None:
                store.update_required_measure(
                    self.measure.id,
                    template_id=self.template_id,
                    template_assessment_id=self.template_assessment_id,
                    **data,
                )
            else:
                hazard_library_template_required_measure_service.update_measure(
                    self.measure.id,
                    template_id=self.template_id,
                    template_assessment_id=self.template_assessment_id,
                    **data,
                )
        except (
            HazardLibraryTemplateExistingMeasureError,
            HazardLibraryTemplateRequiredMeasureError,
        ) as error:
            QMessageBox.warning(self, title, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        data = {
            "description": self.description.toPlainText().strip(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
        if self.relevance is not None:
            data["target_refs"] = self.relevance.selected_refs()
        return data
