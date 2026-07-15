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
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_EXISTING_MEASURE_DIALOG_TITLE,
    HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    HazardLibraryTemplateExistingMeasureError,
    hazard_library_template_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
    HazardLibraryTemplateRequiredMeasureError,
    hazard_library_template_required_measure_service,
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
        title = (
            HAZARD_LIBRARY_EXISTING_MEASURE_DIALOG_TITLE
            if self.measure_type == "existing"
            else HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE
        )
        try:
            if self.measure_type == "existing":
                if self.measure is None:
                    hazard_library_template_existing_measure_service.create_measure(
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
                hazard_library_template_required_measure_service.create_measure(
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
        return {
            "description": self.description.toPlainText().strip(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
