from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal
from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.exposed_group_selector import ExposedGroupSelector
from moduly.nastaveni.ui.exposed_groups_management_dialog import ExposedGroupsManagementDialog
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_SEVERITY,
    RISK_SEVERITIES,
    RISK_SEVERITY_DESCRIPTIONS,
    RISK_SEVERITY_LABELS,
)
from moduly.rizeni_rizik.constants_library import (
    CATALOG_AI_PROPOSAL_EDIT_DIALOG_TITLE,
    CATALOG_AI_PROPOSAL_LEGAL_EDIT_INFO,
    HAZARD_LIBRARY_ASSESSMENT_DIALOG_TITLE,
    HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
    HAZARD_LIBRARY_EXISTING_MEASURE_DIALOG_TITLE,
    HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
    CATALOG_PROPOSAL_KIND_ASSESSMENT,
    CATALOG_PROPOSAL_KIND_EVENT,
    CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
    CATALOG_PROPOSAL_KIND_EXPOSED_GROUP,
    CATALOG_PROPOSAL_KIND_LEGAL,
    CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
    CatalogProposalPayload,
    classify_catalog_proposal,
    merge_payload,
    parse_proposal_payload,
    proposal_payload_to_json,
)


class HazardCatalogAiProposalEditDialog(QDialog):
    def __init__(self, parent=None, *, proposal: AiUnassignedProposal):
        super().__init__(parent)
        self.proposal = proposal
        self.kind = classify_catalog_proposal(proposal)
        self.payload = parse_proposal_payload(proposal)

        titles = {
            CATALOG_PROPOSAL_KIND_EVENT: HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
            CATALOG_PROPOSAL_KIND_ASSESSMENT: HAZARD_LIBRARY_ASSESSMENT_DIALOG_TITLE,
            CATALOG_PROPOSAL_KIND_EXISTING_MEASURE: HAZARD_LIBRARY_EXISTING_MEASURE_DIALOG_TITLE,
            CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE: HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE,
            CATALOG_PROPOSAL_KIND_EXPOSED_GROUP: CATALOG_AI_PROPOSAL_EDIT_DIALOG_TITLE,
            CATALOG_PROPOSAL_KIND_LEGAL: CATALOG_AI_PROPOSAL_EDIT_DIALOG_TITLE,
        }
        self.setWindowTitle(titles.get(self.kind, CATALOG_AI_PROPOSAL_EDIT_DIALOG_TITLE))
        self.resize(620, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit(proposal.name)
        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(70)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(60)
        self.reasoning = QPlainTextEdit(proposal.reasoning or "")
        self.reasoning.setMinimumHeight(70)

        self.exposed_group: ExposedGroupSelector | None = None
        self.manage_groups_btn: QPushButton | None = None
        self.consequence: QPlainTextEdit | None = None
        self.severity: QComboBox | None = None
        self.severity_description = QLabel()
        self.severity_description.setWordWrap(True)
        self.conclusion: QPlainTextEdit | None = None

        if self.kind == CATALOG_PROPOSAL_KIND_EVENT:
            form.addRow("Název události *:", self.name)
            self.description.setPlainText(self.payload.description or proposal.reasoning or "")
            form.addRow("Popis:", self.description)
            self.note.setPlainText(self.payload.note)
            form.addRow("Poznámka:", self.note)
        elif self.kind == CATALOG_PROPOSAL_KIND_ASSESSMENT:
            group_row = QHBoxLayout()
            self.exposed_group = ExposedGroupSelector(self)
            self.manage_groups_btn = QPushButton("Spravovat číselník…")
            self.manage_groups_btn.clicked.connect(self._open_groups_management)
            group_row.addWidget(self.exposed_group, 1)
            group_row.addWidget(self.manage_groups_btn)
            self.consequence = QPlainTextEdit()
            self.consequence.setMinimumHeight(80)
            self.consequence.setPlainText(
                self.payload.consequence or proposal.name or proposal.reasoning or "",
            )
            self.severity = QComboBox()
            for severity in RISK_SEVERITIES:
                self.severity.addItem(RISK_SEVERITY_LABELS[severity], severity)
            severity_value = self.payload.severity or DEFAULT_RISK_SEVERITY
            severity_index = self.severity.findData(severity_value)
            if severity_index >= 0:
                self.severity.setCurrentIndex(severity_index)
            self.severity.currentIndexChanged.connect(self._update_severity_description)
            self.conclusion = QPlainTextEdit()
            self.conclusion.setMinimumHeight(70)
            self.conclusion.setPlainText(self.payload.conclusion)
            self.note.setPlainText(self.payload.note)
            self.exposed_group.reload(preserve_id=proposal.exposed_group_id)
            form.addRow("Ohrožená skupina *:", group_row)
            form.addRow("Možný následek *:", self.consequence)
            form.addRow("Závažnost následku *:", self.severity)
            form.addRow("", self.severity_description)
            form.addRow("Závěr:", self.conclusion)
            form.addRow("Poznámka:", self.note)
            self._update_severity_description()
        elif self.kind in {
            CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
            CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
        }:
            self.description.setPlainText(self.payload.description or proposal.name)
            form.addRow("Popis opatření *:", self.description)
            self.note.setPlainText(self.payload.note or proposal.reasoning or "")
            form.addRow("Poznámka:", self.note)
        elif self.kind == CATALOG_PROPOSAL_KIND_EXPOSED_GROUP:
            form.addRow("Název skupiny *:", self.name)
            self.note.setPlainText(self.payload.note or proposal.reasoning or "")
            form.addRow("Poznámka:", self.note)
        elif self.kind == CATALOG_PROPOSAL_KIND_LEGAL:
            info = QLabel(CATALOG_AI_PROPOSAL_LEGAL_EDIT_INFO)
            info.setWordWrap(True)
            layout.addWidget(info)
            form.addRow("Text návrhu *:", self.name)
            self.reasoning.setPlainText(proposal.reasoning or "")
            form.addRow("Zdůvodnění:", self.reasoning)
        else:
            form.addRow("Název *:", self.name)
            form.addRow("Zdůvodnění:", self.reasoning)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_groups_management(self) -> None:
        if self.exposed_group is None:
            return
        selected_id = self.exposed_group.current_group_id()
        dialog = ExposedGroupsManagementDialog(self)
        dialog.exec()
        self.exposed_group.reload(preserve_id=selected_id)

    def _update_severity_description(self) -> None:
        if self.severity is None:
            return
        severity = self.severity.currentData()
        if severity in RISK_SEVERITY_DESCRIPTIONS:
            self.severity_description.setText(RISK_SEVERITY_DESCRIPTIONS[severity])
        else:
            self.severity_description.setText("")

    def accept(self) -> None:
        if self.kind == CATALOG_PROPOSAL_KIND_ASSESSMENT and self.exposed_group is not None:
            group_id = self.exposed_group.ensure_selected_group_id(self)
            if group_id is None:
                QMessageBox.warning(
                    self,
                    self.windowTitle(),
                    "Vyberte nebo vytvořte ohroženou skupinu.",
                )
                return
            self.proposal.exposed_group_id = group_id

        if self.kind == CATALOG_PROPOSAL_KIND_EVENT:
            if not self.name.text().strip():
                QMessageBox.warning(self, self.windowTitle(), "Název události je povinný.")
                return
            self.proposal.name = self.name.text().strip()
            self.payload = merge_payload(
                self.payload,
                {
                    "description": self.description.toPlainText().strip(),
                    "note": self.note.toPlainText().strip(),
                },
            )
        elif self.kind == CATALOG_PROPOSAL_KIND_ASSESSMENT:
            assert self.consequence is not None and self.severity is not None
            if not self.consequence.toPlainText().strip():
                QMessageBox.warning(self, self.windowTitle(), "Možný následek je povinný.")
                return
            self.proposal.name = self.consequence.toPlainText().strip()
            self.payload = merge_payload(
                self.payload,
                {
                    "consequence": self.consequence.toPlainText().strip(),
                    "severity": self.severity.currentData(),
                    "conclusion": self.conclusion.toPlainText().strip() if self.conclusion else "",
                    "note": self.note.toPlainText().strip(),
                },
            )
        elif self.kind in {
            CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
            CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
        }:
            if not self.description.toPlainText().strip():
                QMessageBox.warning(self, self.windowTitle(), "Popis opatření je povinný.")
                return
            self.proposal.name = self.description.toPlainText().strip()
            self.payload = merge_payload(
                self.payload,
                {
                    "description": self.description.toPlainText().strip(),
                    "note": self.note.toPlainText().strip(),
                },
            )
        elif self.kind in {CATALOG_PROPOSAL_KIND_EXPOSED_GROUP, CATALOG_PROPOSAL_KIND_LEGAL}:
            if not self.name.text().strip():
                QMessageBox.warning(self, self.windowTitle(), "Text návrhu je povinný.")
                return
            self.proposal.name = self.name.text().strip()
            self.proposal.reasoning = self.reasoning.toPlainText().strip()
            self.payload = merge_payload(
                self.payload,
                {"note": self.note.toPlainText().strip() if self.kind == CATALOG_PROPOSAL_KIND_EXPOSED_GROUP else ""},
            )
        else:
            if not self.name.text().strip():
                QMessageBox.warning(self, self.windowTitle(), "Název je povinný.")
                return
            self.proposal.name = self.name.text().strip()
            self.proposal.reasoning = self.reasoning.toPlainText().strip()

        self.proposal.payload_json = proposal_payload_to_json(self.payload)
        ai_peer_review_service.update_proposal(self.proposal)
        super().accept()
