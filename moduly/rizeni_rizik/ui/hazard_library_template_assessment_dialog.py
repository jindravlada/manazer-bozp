from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.multi_exposed_group_selector import MultiExposedGroupSelector
from core.widgets.severity_tooltips import (
    bind_severity_combo_tooltip,
    populate_severity_combo,
    severity_description_for_combo,
)
from moduly.nastaveni.ui.exposed_groups_management_dialog import ExposedGroupsManagementDialog
from moduly.rizeni_rizik.constants import DEFAULT_RISK_SEVERITY
from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_ASSESSMENT_DIALOG_TITLE
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    HazardLibraryTemplateAssessmentError,
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_working_copy import (
    find_catalog_working_copy,
)


class HazardLibraryTemplateAssessmentDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        template_id: int,
        template_event_id: int,
        assessment=None,
        read_only: bool = False,
    ):
        super().__init__(parent)

        self.template_id = template_id
        self.template_event_id = template_event_id
        self.assessment = assessment
        self.read_only = read_only
        self.saved_assessment = assessment

        self.setWindowTitle(HAZARD_LIBRARY_ASSESSMENT_DIALOG_TITLE)
        self.resize(620, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        group_row = QHBoxLayout()
        self.exposed_groups = MultiExposedGroupSelector(self)
        self.manage_groups_btn = QPushButton("Spravovat číselník…")
        self.manage_groups_btn.clicked.connect(self._open_groups_management)
        group_row.addWidget(self.exposed_groups, 1)
        group_row.addWidget(self.manage_groups_btn)

        self.severity = QComboBox()
        populate_severity_combo(self.severity)
        self.severity_description = QLabel()
        self.severity_description.setWordWrap(True)
        self.severity.currentIndexChanged.connect(self._update_severity_description)
        bind_severity_combo_tooltip(self.severity)
        self.conclusion = QPlainTextEdit()
        self.conclusion.setMinimumHeight(80)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(60)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Ohrožené skupiny *:", group_row)
        form.addRow("Závažnost následku *:", self.severity)
        form.addRow("", self.severity_description)
        form.addRow("Závěr:", self.conclusion)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if assessment is not None:
            store = find_catalog_working_copy(self)
            if store is not None:
                group_ids = store.get_group_ids(assessment.id)
            else:
                group_ids = hazard_library_template_assessment_service.get_group_ids(
                    assessment.id,
                )
            if not group_ids and assessment.exposed_group_id:
                group_ids = [assessment.exposed_group_id]
            self.exposed_groups.set_group_ids(group_ids)
            severity_index = self.severity.findData(assessment.severity)
            if severity_index >= 0:
                self.severity.setCurrentIndex(severity_index)
            self.conclusion.setPlainText(assessment.conclusion or "")
            self.note.setPlainText(assessment.note or "")
            self.active_checkbox.setChecked(bool(assessment.active))
        else:
            self.severity.setCurrentIndex(self.severity.findData(DEFAULT_RISK_SEVERITY))

        self._update_severity_description()

        if read_only:
            self.exposed_groups.setEnabled(False)
            self.manage_groups_btn.setEnabled(False)
            self.severity.setEnabled(False)
            self.conclusion.setReadOnly(True)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _open_groups_management(self) -> None:
        selected_ids = self.exposed_groups.selected_group_ids()
        dialog = ExposedGroupsManagementDialog(self)
        dialog.exec()
        self.exposed_groups.reload(preserve_ids=selected_ids)

    def _update_severity_description(self) -> None:
        self.severity_description.setText(severity_description_for_combo(self.severity))

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        data = self.get_data()
        if not data["exposed_group_ids"]:
            QMessageBox.warning(
                self,
                HAZARD_LIBRARY_ASSESSMENT_DIALOG_TITLE,
                "Vyberte alespoň jednu ohroženou skupinu.",
            )
            return

        try:
            store = find_catalog_working_copy(self)
            if self.assessment is None:
                if store is not None:
                    self.saved_assessment = store.create_assessment(
                        template_id=self.template_id,
                        template_event_id=self.template_event_id,
                        **data,
                    )
                else:
                    self.saved_assessment = (
                        hazard_library_template_assessment_service.create_assessment(
                            template_id=self.template_id,
                            template_event_id=self.template_event_id,
                            **data,
                        )
                    )
            elif store is not None:
                self.saved_assessment = store.update_assessment(
                    self.assessment.id,
                    template_id=self.template_id,
                    template_event_id=self.template_event_id,
                    **data,
                )
            else:
                self.saved_assessment = (
                    hazard_library_template_assessment_service.update_assessment(
                        self.assessment.id,
                        template_id=self.template_id,
                        template_event_id=self.template_event_id,
                        **data,
                    )
                )
        except HazardLibraryTemplateAssessmentError as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_ASSESSMENT_DIALOG_TITLE, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "exposed_group_ids": self.exposed_groups.selected_group_ids(),
            "severity": self.severity.currentData(),
            "conclusion": self.conclusion.toPlainText().strip(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
