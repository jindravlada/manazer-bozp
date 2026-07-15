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
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.nastaveni.ui.exposed_groups_management_dialog import ExposedGroupsManagementDialog
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_ASSESSMENT_STATUS,
    DEFAULT_RISK_SEVERITY,
    HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
    RISK_ASSESSMENT_STATUS_COMPLETED,
    RISK_ASSESSMENT_STATUS_DRAFT,
    RISK_ASSESSMENT_STATUSES,
    RISK_ASSESSMENT_STATUS_LABELS,
    RISK_SEVERITIES,
    RISK_SEVERITY_DESCRIPTIONS,
    RISK_SEVERITY_LABELS,
)
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
        self.resize(620, 560)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.event = QComboBox()
        self._populate_events(default_hazard_event_id)

        group_row = QHBoxLayout()
        self.exposed_group = QComboBox()
        self.manage_groups_btn = QPushButton("Spravovat číselník…")
        self.manage_groups_btn.clicked.connect(self._open_groups_management)
        group_row.addWidget(self.exposed_group, 1)
        group_row.addWidget(self.manage_groups_btn)

        self.consequence = QPlainTextEdit()
        self.consequence.setMinimumHeight(80)
        self.severity = QComboBox()
        for severity in RISK_SEVERITIES:
            self.severity.addItem(RISK_SEVERITY_LABELS[severity], severity)
        self.severity_description = QLabel()
        self.severity_description.setWordWrap(True)
        self.severity.currentIndexChanged.connect(self._update_severity_description)
        self.assessment_status = QComboBox()
        for status in RISK_ASSESSMENT_STATUSES:
            self.assessment_status.addItem(RISK_ASSESSMENT_STATUS_LABELS[status], status)
        self.conclusion = QPlainTextEdit()
        self.conclusion.setMinimumHeight(80)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(60)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Nežádoucí událost *:", self.event)
        form.addRow("Ohrožená skupina *:", group_row)
        form.addRow("Možný následek *:", self.consequence)
        form.addRow("Závažnost následku *:", self.severity)
        form.addRow("", self.severity_description)
        form.addRow("Stav posouzení:", self.assessment_status)
        form.addRow("Závěr posouzení:", self.conclusion)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        selected_group_id = assessment.exposed_group_id if assessment is not None else None
        self._reload_exposed_groups(selected_group_id=selected_group_id)

        if assessment is not None:
            index = self.event.findData(assessment.hazard_event_id)
            if index >= 0:
                self.event.setCurrentIndex(index)
            self.consequence.setPlainText(assessment.consequence or "")
            severity_index = self.severity.findData(assessment.severity)
            if severity_index >= 0:
                self.severity.setCurrentIndex(severity_index)
            status_index = self.assessment_status.findData(assessment.assessment_status)
            if status_index >= 0:
                self.assessment_status.setCurrentIndex(status_index)
            self.conclusion.setPlainText(assessment.conclusion or "")
            self.note.setPlainText(assessment.note or "")
            self.active_checkbox.setChecked(bool(assessment.active))
        else:
            default_index = self.severity.findData(DEFAULT_RISK_SEVERITY)
            if default_index >= 0:
                self.severity.setCurrentIndex(default_index)
            default_status_index = self.assessment_status.findData(
                DEFAULT_RISK_ASSESSMENT_STATUS
            )
            if default_status_index >= 0:
                self.assessment_status.setCurrentIndex(default_status_index)

        self._update_severity_description()

        if read_only:
            self.event.setEnabled(False)
            self.exposed_group.setEnabled(False)
            self.manage_groups_btn.setEnabled(False)
            self.consequence.setReadOnly(True)
            self.severity.setEnabled(False)
            self.assessment_status.setEnabled(False)
            self.conclusion.setReadOnly(True)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _reload_exposed_groups(self, *, selected_group_id: int | None) -> None:
        current_id = selected_group_id or self.exposed_group.currentData()
        self.exposed_group.clear()
        for group in exposed_group_service.get_active_all():
            self.exposed_group.addItem(group.name, group.id)
        if selected_group_id is not None:
            index = self.exposed_group.findData(selected_group_id)
            if index >= 0:
                self.exposed_group.setCurrentIndex(index)
            else:
                group = exposed_group_service.get_by_id(selected_group_id)
                if group is not None:
                    label = f"{group.name} (neaktivní)"
                    self.exposed_group.addItem(label, group.id)
                    self.exposed_group.setCurrentIndex(self.exposed_group.count() - 1)
        elif current_id is not None:
            index = self.exposed_group.findData(current_id)
            if index >= 0:
                self.exposed_group.setCurrentIndex(index)

    def _open_groups_management(self) -> None:
        selected_id = self.exposed_group.currentData()
        dialog = ExposedGroupsManagementDialog(self)
        dialog.exec()
        self._reload_exposed_groups(selected_group_id=selected_id)

    def _populate_events(self, default_hazard_event_id: int | None) -> None:
        rows = hazard_risk_assessment_service.get_event_candidates(
            self.hazard_identification_id
        )
        self.event.clear()
        for row in rows:
            label = f"{row.event.name} ({row.inventory_item_name})"
            self.event.addItem(label, row.event.id)

        if default_hazard_event_id is not None:
            index = self.event.findData(default_hazard_event_id)
            if index >= 0:
                self.event.setCurrentIndex(index)

    def _update_severity_description(self) -> None:
        severity = self.severity.currentData()
        description = RISK_SEVERITY_DESCRIPTIONS.get(severity, "")
        self.severity_description.setText(description)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        data = self.get_data()
        old_status = (
            self.risk_assessment.assessment_status
            if self.risk_assessment is not None
            else DEFAULT_RISK_ASSESSMENT_STATUS
        )
        new_status = data["assessment_status"]

        if (
            new_status == RISK_ASSESSMENT_STATUS_COMPLETED
            and old_status != RISK_ASSESSMENT_STATUS_COMPLETED
        ):
            reply = QMessageBox.question(
                self,
                HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
                "Označit toto posouzení jako dokončené?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        if (
            new_status == RISK_ASSESSMENT_STATUS_DRAFT
            and old_status == RISK_ASSESSMENT_STATUS_COMPLETED
        ):
            reply = QMessageBox.question(
                self,
                HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
                "Vrátit posouzení do stavu Rozpracováno?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

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
            "exposed_group_id": self.exposed_group.currentData(),
            "consequence": self.consequence.toPlainText().strip(),
            "severity": self.severity.currentData(),
            "assessment_status": self.assessment_status.currentData(),
            "conclusion": self.conclusion.toPlainText().strip(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
