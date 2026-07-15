"""Editor celého návrhového balíku AI (R20b)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
    AI_PEER_REVIEW_PACKAGE_TYPE_LABELS,
    AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
)
from core.ai_oponentni.proposal_package_types import (
    AiProposalPackage,
    AiProposalPackageAssessment,
    AiProposalPackageEvent,
    AiProposalPackageLegalLink,
    AiProposalPackageMeasure,
)
from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.exposed_group_selector import ExposedGroupSelector
from moduly.nastaveni.ui.exposed_groups_management_dialog import ExposedGroupsManagementDialog
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_SEVERITY,
    RISK_SEVERITIES,
    RISK_SEVERITY_LABELS,
)
from moduly.rizeni_rizik.constants_library import CATALOG_AI_PACKAGE_EDIT_DIALOG_TITLE
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
    hazard_catalog_proposal_incorporate_service,
)


class _AssessmentEditor(QGroupBox):
    def __init__(self, parent=None, *, assessment: AiProposalPackageAssessment | None = None):
        super().__init__("Posouzení", parent)
        layout = QFormLayout(self)

        group_row = QHBoxLayout()
        self.exposed_group = ExposedGroupSelector(self)
        self.manage_groups_btn = QPushButton("Spravovat číselník…")
        self.manage_groups_btn.clicked.connect(self._open_groups_management)
        group_row.addWidget(self.exposed_group, 1)
        group_row.addWidget(self.manage_groups_btn)

        self.consequence = QPlainTextEdit()
        self.consequence.setMinimumHeight(60)
        self.severity = QComboBox()
        for severity in RISK_SEVERITIES:
            self.severity.addItem(RISK_SEVERITY_LABELS[severity], severity)
        self.conclusion = QPlainTextEdit()
        self.conclusion.setMinimumHeight(50)
        self.existing_measures = QPlainTextEdit()
        self.existing_measures.setPlaceholderText("Jedno opatření na řádek")
        self.existing_measures.setMinimumHeight(60)
        self.required_measures = QPlainTextEdit()
        self.required_measures.setPlaceholderText("Jedno opatření na řádek")
        self.required_measures.setMinimumHeight(60)

        layout.addRow("Ohrožená skupina *:", group_row)
        layout.addRow("Možný následek *:", self.consequence)
        layout.addRow("Závažnost *:", self.severity)
        layout.addRow("Závěr:", self.conclusion)
        layout.addRow("Existující opatření:", self.existing_measures)
        layout.addRow("Potřebná opatření:", self.required_measures)

        if assessment is not None:
            self.exposed_group.reload(preserve_id=assessment.exposed_group_id)
            if assessment.exposed_group_id is None and assessment.exposed_group.strip():
                self.exposed_group.setCurrentText(assessment.exposed_group)
            self.consequence.setPlainText(assessment.consequence)
            severity_index = self.severity.findData(
                assessment.severity if assessment.severity in RISK_SEVERITIES else DEFAULT_RISK_SEVERITY,
            )
            if severity_index >= 0:
                self.severity.setCurrentIndex(severity_index)
            self.conclusion.setPlainText(assessment.conclusion)
            self.existing_measures.setPlainText(
                "\n".join(m.description for m in assessment.existing_measures),
            )
            self.required_measures.setPlainText(
                "\n".join(m.description for m in assessment.required_measures),
            )
        else:
            self.exposed_group.reload()
            severity_index = self.severity.findData(DEFAULT_RISK_SEVERITY)
            if severity_index >= 0:
                self.severity.setCurrentIndex(severity_index)

    def _open_groups_management(self) -> None:
        dialog = ExposedGroupsManagementDialog(self)
        dialog.exec()
        self.exposed_group.reload(preserve_id=self.exposed_group.current_group_id())

    def to_assessment(self) -> AiProposalPackageAssessment:
        group_id = self.exposed_group.current_group_id()
        group_name = (self.exposed_group.currentText() or "").strip()
        if group_id is not None:
            from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service

            group_name = exposed_group_service.display_name(group_id) or group_name
        return AiProposalPackageAssessment(
            exposed_group=group_name,
            consequence=self.consequence.toPlainText().strip(),
            severity=self.severity.currentData() or DEFAULT_RISK_SEVERITY,
            conclusion=self.conclusion.toPlainText().strip(),
            exposed_group_id=group_id,
            existing_measures=tuple(
                AiProposalPackageMeasure(description=line.strip())
                for line in self.existing_measures.toPlainText().splitlines()
                if line.strip()
            ),
            required_measures=tuple(
                AiProposalPackageMeasure(description=line.strip())
                for line in self.required_measures.toPlainText().splitlines()
                if line.strip()
            ),
        )


class HazardCatalogAiPackageEditDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        package: AiProposalPackage,
        package_record_id: int,
    ):
        super().__init__(parent)
        self._package = package
        self._package_record_id = package_record_id
        self._result_package: AiProposalPackage | None = None
        self.setWindowTitle(CATALOG_AI_PACKAGE_EDIT_DIALOG_TITLE)
        self.resize(720, 740)

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        type_label = AI_PEER_REVIEW_PACKAGE_TYPE_LABELS.get(
            package.package_type,
            package.package_type,
        )
        layout.addWidget(QLabel(f"ID balíku: {package.package_id}"))
        layout.addWidget(QLabel(f"Typ: {type_label}"))

        event_box = QGroupBox("Událost")
        event_form = QFormLayout(event_box)
        self.event_name = QLineEdit()
        self.event_description = QPlainTextEdit()
        self.event_description.setMinimumHeight(60)
        self.event_note = QPlainTextEdit()
        self.event_note.setMinimumHeight(50)
        self.target_event = QLineEdit(package.target_event_export_id or "")

        if package.package_type == AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT:
            event_form.addRow("Cílová událost (EVENT-…):", self.target_event)
            if package.event is not None:
                self.event_name.setText(package.event.name)
                self.event_description.setPlainText(package.event.description)
                self.event_note.setPlainText(package.event.note)
        else:
            if package.event is not None:
                self.event_name.setText(package.event.name)
                self.event_description.setPlainText(package.event.description)
                self.event_note.setPlainText(package.event.note)
            event_form.addRow("Název události *:", self.event_name)
            event_form.addRow("Popis:", self.event_description)
            event_form.addRow("Poznámka:", self.event_note)
        layout.addWidget(event_box)

        assessments_box = QGroupBox("Posouzení")
        assessments_layout = QVBoxLayout(assessments_box)
        self._assessment_editors: list[_AssessmentEditor] = []
        for assessment in package.assessments or (
            AiProposalPackageAssessment(
                exposed_group="",
                consequence="",
                severity=DEFAULT_RISK_SEVERITY,
            ),
        ):
            editor = _AssessmentEditor(assessment=assessment)
            self._assessment_editors.append(editor)
            assessments_layout.addWidget(editor)
        add_assessment_btn = QPushButton("Přidat posouzení")
        add_assessment_btn.clicked.connect(self._add_assessment)
        assessments_layout.addWidget(add_assessment_btn)
        layout.addWidget(assessments_box)

        legal_box = QGroupBox("Právní vazby")
        legal_layout = QVBoxLayout(legal_box)
        legal_layout.addWidget(
            QLabel("Každý řádek: odkaz. Volitelně vyberte požadavek z registru."),
        )
        self.legal_references = QPlainTextEdit()
        self.legal_references.setMinimumHeight(70)
        self.legal_references.setPlainText(
            "\n".join(link.reference for link in package.legal_links),
        )
        legal_layout.addWidget(self.legal_references)

        self.legal_document = QComboBox()
        self.legal_document.addItem("— bez výběru z registru —", None)
        for document_id, label in (
            hazard_catalog_proposal_incorporate_service.list_legal_document_candidates()
        ):
            self.legal_document.addItem(label, document_id)
        selected_document_id = None
        if package.legal_links:
            selected_document_id = package.legal_links[0].legal_document_id
        if selected_document_id is not None:
            index = self.legal_document.findData(selected_document_id)
            if index >= 0:
                self.legal_document.setCurrentIndex(index)
        legal_layout.addWidget(QLabel("Mapovat první řádek na předpis:"))
        legal_layout.addWidget(self.legal_document)
        layout.addWidget(legal_box)

        self.reasoning = QPlainTextEdit(package.reasoning or "")
        self.reasoning.setMinimumHeight(80)
        layout.addWidget(QLabel("Zdůvodnění AI:"))
        layout.addWidget(self.reasoning)

        scroll.setWidget(content)
        root.addWidget(scroll)

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText("Uložit balík")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _add_assessment(self) -> None:
        editor = _AssessmentEditor()
        self._assessment_editors.append(editor)
        # Insert before the "Přidat posouzení" button's parent layout last widgets.
        parent = self._assessment_editors[0].parentWidget()
        if parent is not None and parent.layout() is not None:
            layout = parent.layout()
            layout.insertWidget(layout.count() - 1, editor)

    def get_package(self) -> AiProposalPackage | None:
        return self._result_package

    def accept(self) -> None:
        assessments: list[AiProposalPackageAssessment] = []
        for editor in self._assessment_editors:
            assessment = editor.to_assessment()
            if not assessment.exposed_group.strip():
                QMessageBox.warning(self, self.windowTitle(), "Vyplňte ohroženou skupinu.")
                return
            if not assessment.consequence.strip():
                QMessageBox.warning(self, self.windowTitle(), "Vyplňte možný následek.")
                return
            assessments.append(assessment)
        if not assessments:
            QMessageBox.warning(self, self.windowTitle(), "Balík musí mít alespoň jedno posouzení.")
            return

        event = None
        target_event = None
        if self._package.package_type == AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT:
            name = self.event_name.text().strip()
            if not name:
                QMessageBox.warning(self, self.windowTitle(), "Vyplňte název události.")
                return
            event = AiProposalPackageEvent(
                name=name,
                description=self.event_description.toPlainText().strip(),
                note=self.event_note.toPlainText().strip(),
            )
        else:
            target_event = self.target_event.text().strip() or None
            if not target_event:
                QMessageBox.warning(self, self.windowTitle(), "Vyplňte cílovou událost EVENT-…")
                return
            if self.event_name.text().strip():
                event = AiProposalPackageEvent(
                    name=self.event_name.text().strip(),
                    description=self.event_description.toPlainText().strip(),
                    note=self.event_note.toPlainText().strip(),
                )

        legal_links: list[AiProposalPackageLegalLink] = []
        selected_document_id = self.legal_document.currentData()
        for index, line in enumerate(self.legal_references.toPlainText().splitlines()):
            reference = line.strip()
            if not reference:
                continue
            legal_links.append(
                AiProposalPackageLegalLink(
                    reference=reference,
                    legal_document_id=(
                        selected_document_id if index == 0 else None
                    ),
                ),
            )

        self._result_package = AiProposalPackage(
            package_id=self._package.package_id,
            package_type=self._package.package_type,
            target_event_export_id=target_event,
            event=event,
            assessments=tuple(assessments),
            legal_links=tuple(legal_links),
            reasoning=self.reasoning.toPlainText().strip(),
        )
        super().accept()
