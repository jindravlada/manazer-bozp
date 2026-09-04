"""Editor doporučení k opatření z AI oponentury (schema 2.0)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_LABELS
from core.ai_oponentni.proposal_package_types import AiProposalPackage
from core.ai_oponentni.repository.ai_proposal_package_repository import (
    AiProposalPackageRepository,
)
from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants_library import (
    CATALOG_AI_MEASURE_REC_EDIT_DIALOG_TITLE,
    CATALOG_AI_MEASURE_REC_PROPOSED_REQUIRED,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
    hazard_catalog_package_incorporate_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    hazard_library_template_event_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    hazard_library_template_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
    hazard_library_template_required_measure_service,
)


@dataclass(frozen=True)
class MeasureRecommendationTargetInfo:
    type_label: str
    target_export_id: str
    event_name: str
    assessment_label: str
    current_text: str
    target_found: bool

    @property
    def target_summary(self) -> str:
        parts = [part for part in (self.event_name, self.assessment_label) if part]
        if parts:
            return " — ".join(parts)
        if self.target_export_id:
            return self.target_export_id
        return "—"


def resolve_measure_recommendation_target(
    package: AiProposalPackage,
    *,
    package_record_id: int | None = None,
    review_id: int | None = None,
) -> MeasureRecommendationTargetInfo:
    """Lidský popis cíle doporučení podle export_id_map konzultace."""
    type_label = AI_PEER_REVIEW_PACKAGE_TYPE_LABELS.get(
        package.package_type,
        package.package_type,
    )
    target_export_id = (package.target_export_id or "").strip()
    info = MeasureRecommendationTargetInfo(
        type_label=type_label,
        target_export_id=target_export_id,
        event_name="",
        assessment_label="",
        current_text="",
        target_found=False,
    )
    if not target_export_id:
        return info

    resolved_review_id = review_id
    if resolved_review_id is None and package_record_id:
        record = AiProposalPackageRepository().get_by_id(package_record_id)
        if record is not None:
            resolved_review_id = record.ai_peer_review_id
    if resolved_review_id is None:
        return info

    export_map = hazard_catalog_package_incorporate_service.get_export_id_map(
        resolved_review_id,
    )
    payload = export_map.get(target_export_id)
    if not isinstance(payload, dict) or payload.get("id") is None:
        return info

    kind = str(payload.get("kind") or "")
    entity_id = int(payload["id"])
    event_name = ""
    assessment_label = ""
    current_text = ""
    assessment = None
    measure = None

    if kind == "existing_measure":
        measure = hazard_library_template_existing_measure_service.get_by_id(entity_id)
        if measure is not None:
            current_text = measure.description or ""
            assessment = hazard_library_template_assessment_service.get_by_id(
                measure.template_assessment_id,
            )
    elif kind == "required_measure":
        measure = hazard_library_template_required_measure_service.get_by_id(entity_id)
        if measure is not None:
            current_text = measure.description or ""
            assessment = hazard_library_template_assessment_service.get_by_id(
                measure.template_assessment_id,
            )
    elif kind == "assessment":
        assessment = hazard_library_template_assessment_service.get_by_id(entity_id)

    if assessment is not None:
        assessment_label = (
            hazard_library_template_assessment_service.get_exposed_group_display_name(
                assessment,
            )
            or ""
        )
        if assessment_label == "—":
            assessment_label = ""
        event = hazard_library_template_event_service.get_by_id(
            assessment.template_event_id,
        )
        if event is not None:
            event_name = (event.name or "").strip()

    target_found = bool(measure is not None or assessment is not None)
    return MeasureRecommendationTargetInfo(
        type_label=type_label,
        target_export_id=target_export_id,
        event_name=event_name,
        assessment_label=assessment_label,
        current_text=current_text.strip(),
        target_found=target_found,
    )


class HazardCatalogAiMeasureRecommendationEditDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        package: AiProposalPackage,
        package_record_id: int = 0,
        review_id: int | None = None,
    ):
        super().__init__(parent)
        self._package = package
        self._package_record_id = package_record_id
        self._result_package: AiProposalPackage | None = None
        self._target = resolve_measure_recommendation_target(
            package,
            package_record_id=package_record_id if package_record_id else None,
            review_id=review_id,
        )

        self.setWindowTitle(CATALOG_AI_MEASURE_REC_EDIT_DIALOG_TITLE)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(620, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.type_field = QLineEdit(self._target.type_label)
        self.type_field.setReadOnly(True)
        form.addRow("Typ návrhu:", self.type_field)

        self.target_field = QPlainTextEdit(self._target.target_summary)
        self.target_field.setReadOnly(True)
        self.target_field.setMinimumHeight(48)
        self.target_field.setMaximumHeight(80)
        form.addRow("Cíl:", self.target_field)

        current_text = self._target.current_text or "—"
        self.current_text = QPlainTextEdit(current_text)
        self.current_text.setReadOnly(True)
        self.current_text.setMinimumHeight(70)
        self.current_text.setMaximumHeight(140)
        form.addRow("Současné znění:", self.current_text)

        self.proposed_text = QPlainTextEdit(package.proposed_text or "")
        self.proposed_text.setMinimumHeight(90)
        self.proposed_text.setTabChangesFocus(True)
        form.addRow("Navrhované znění *:", self.proposed_text)

        self.reasoning = QPlainTextEdit(package.reasoning or "")
        self.reasoning.setMinimumHeight(90)
        self.reasoning.setTabChangesFocus(True)
        form.addRow("Zdůvodnění:", self.reasoning)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def incorporate_requested(self) -> bool:
        return False

    def get_package(self) -> AiProposalPackage | None:
        return self._result_package

    def accept(self) -> None:
        proposed = self.proposed_text.toPlainText().strip()
        if not proposed:
            QMessageBox.warning(
                self,
                CATALOG_AI_MEASURE_REC_EDIT_DIALOG_TITLE,
                CATALOG_AI_MEASURE_REC_PROPOSED_REQUIRED,
            )
            self.proposed_text.setFocus()
            return
        self._result_package = self._package.with_editable_measure_fields(
            proposed_text=proposed,
            reasoning=self.reasoning.toPlainText(),
        )
        super().accept()
