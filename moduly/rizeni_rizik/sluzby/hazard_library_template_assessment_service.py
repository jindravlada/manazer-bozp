from dataclasses import dataclass
from datetime import datetime

from core.utils.czech_sort import czech_sorted
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.rizeni_rizik.constants import (
    RISK_SEVERITIES,
    format_risk_severity_label,
)
from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
    HazardLibraryTemplateAssessment,
)
from moduly.rizeni_rizik.repository.hazard_library_template_assessment_repository import (
    HazardLibraryTemplateAssessmentRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    hazard_library_template_event_service,
)


class HazardLibraryTemplateAssessmentError(ValueError):
    pass


@dataclass
class HazardLibraryTemplateAssessmentRow:
    assessment: HazardLibraryTemplateAssessment
    exposed_group_name: str
    severity_label: str


class HazardLibraryTemplateAssessmentService:
    def __init__(self):
        self.repository = HazardLibraryTemplateAssessmentRepository()

    def get_exposed_group_display_name(
        self,
        assessment: HazardLibraryTemplateAssessment,
    ) -> str:
        name = exposed_group_service.display_name(assessment.exposed_group_id)
        return name or "—"

    def get_for_event(
        self,
        template_event_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateAssessmentRow]:
        assessments = self.repository.get_for_event(
            template_event_id,
            include_inactive=include_inactive,
        )
        rows = [self._to_row(assessment) for assessment in assessments]
        return self._sort_rows(rows)

    def get_by_id(self, assessment_id: int | None) -> HazardLibraryTemplateAssessment | None:
        if not assessment_id:
            return None
        return self.repository.get_by_id(assessment_id)

    def count_active_for_event(self, template_event_id: int) -> int:
        return self.repository.count_active_for_event(template_event_id)

    def count_active_by_events(self, template_id: int) -> dict[int, int]:
        counts: dict[int, int] = {}
        for event in hazard_library_template_event_service.get_for_template(
            template_id,
            include_inactive=True,
        ):
            counts[event.id] = self.repository.count_active_for_event(event.id)
        return counts

    def create_assessment(
        self,
        *,
        template_id: int,
        template_event_id: int,
        exposed_group_id: int,
        consequence: str,
        severity: str,
        conclusion: str = "",
        note: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateAssessment:
        validated_group_id = self._validate_exposed_group_id(exposed_group_id)
        normalized_consequence = self._validate_consequence(consequence)
        normalized_severity = self._validate_severity(severity)

        self._validate_event(template_id, template_event_id)
        self._validate_unique_active_group(
            template_event_id,
            exposed_group_id=validated_group_id,
            exclude_assessment_id=None,
            active=active,
        )

        assessment = HazardLibraryTemplateAssessment(
            template_event_id=template_event_id,
            exposed_group_id=validated_group_id,
            consequence=normalized_consequence,
            severity=normalized_severity,
            conclusion=conclusion.strip(),
            note=note.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(template_event_id),
        )
        saved = self.repository.add(assessment)
        return saved

    def update_assessment(
        self,
        assessment_id: int,
        *,
        template_id: int,
        template_event_id: int,
        exposed_group_id: int,
        consequence: str,
        severity: str,
        conclusion: str = "",
        note: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateAssessment | None:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return None

        validated_group_id = self._validate_exposed_group_id(exposed_group_id)
        normalized_consequence = self._validate_consequence(consequence)
        normalized_severity = self._validate_severity(severity)

        self._validate_event(template_id, template_event_id)
        self._validate_unique_active_group(
            template_event_id,
            exposed_group_id=validated_group_id,
            exclude_assessment_id=assessment_id,
            active=active,
        )

        assessment.template_event_id = template_event_id
        assessment.exposed_group_id = validated_group_id
        assessment.consequence = normalized_consequence
        assessment.severity = normalized_severity
        assessment.conclusion = conclusion.strip()
        assessment.note = note.strip()
        assessment.active = active
        assessment.updated_at = datetime.now()
        saved = self.repository.update(assessment)
        return saved

    def activate_assessment(self, assessment_id: int) -> bool:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return False
        self._validate_unique_active_group(
            assessment.template_event_id,
            exposed_group_id=assessment.exposed_group_id,
            exclude_assessment_id=assessment_id,
            active=True,
        )
        assessment.active = True
        assessment.updated_at = datetime.now()
        self.repository.update(assessment)
        return True

    def deactivate_assessment(self, assessment_id: int) -> bool:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return False
        assessment.active = False
        assessment.updated_at = datetime.now()
        self.repository.update(assessment)
        return True

    def get_template_id_for_assessment(self, assessment_id: int) -> int | None:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return None
        return self._template_id_for_assessment(assessment)

    def _template_id_for_assessment(self, assessment: HazardLibraryTemplateAssessment) -> int:
        template_id = hazard_library_template_event_service.get_template_id_for_event(
            assessment.template_event_id
        )
        if template_id is None:
            raise HazardLibraryTemplateAssessmentError("Nežádoucí událost zdroje rizika neexistuje.")
        return template_id

    def _to_row(self, assessment: HazardLibraryTemplateAssessment) -> HazardLibraryTemplateAssessmentRow:
        return HazardLibraryTemplateAssessmentRow(
            assessment=assessment,
            exposed_group_name=self.get_exposed_group_display_name(assessment),
            severity_label=format_risk_severity_label(assessment.severity),
        )

    def _sort_rows(
        self,
        rows: list[HazardLibraryTemplateAssessmentRow],
    ) -> list[HazardLibraryTemplateAssessmentRow]:
        return czech_sorted(rows, key=lambda row: row.exposed_group_name.casefold())

    def _validate_exposed_group_id(self, exposed_group_id: int | None) -> int:
        if not exposed_group_id:
            raise HazardLibraryTemplateAssessmentError("Ohrožená skupina je povinná.")
        group = exposed_group_service.get_by_id(exposed_group_id)
        if group is None:
            raise HazardLibraryTemplateAssessmentError("Vybraná ohrožená skupina neexistuje.")
        if not group.active:
            raise HazardLibraryTemplateAssessmentError(
                "Lze vybrat pouze aktivní ohroženou skupinu z číselníku."
            )
        return group.id

    def _validate_consequence(self, consequence: str) -> str:
        normalized_consequence = consequence.strip()
        if not normalized_consequence:
            raise HazardLibraryTemplateAssessmentError("Možný následek je povinný.")
        return normalized_consequence

    def _validate_severity(self, severity: str) -> str:
        if severity not in RISK_SEVERITIES:
            raise HazardLibraryTemplateAssessmentError("Neplatná závažnost následku.")
        return severity

    def _validate_event(self, template_id: int, template_event_id: int) -> None:
        event = hazard_library_template_event_service.get_by_id(template_event_id)
        if event is None:
            raise HazardLibraryTemplateAssessmentError("Nežádoucí událost zdroje rizika neexistuje.")
        event_template_id = hazard_library_template_event_service.get_template_id_for_event(
            event.id
        )
        if event_template_id != template_id:
            raise HazardLibraryTemplateAssessmentError(
                "Nežádoucí událost nepatří do zvoleného zdroje rizika."
            )

    def _validate_unique_active_group(
        self,
        template_event_id: int,
        *,
        exposed_group_id: int,
        exclude_assessment_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        for assessment in self.repository.get_for_event(template_event_id, include_inactive=True):
            if assessment.id == exclude_assessment_id:
                continue
            if not assessment.active:
                continue
            if assessment.exposed_group_id == exposed_group_id:
                group_name = exposed_group_service.display_name(exposed_group_id) or "—"
                raise HazardLibraryTemplateAssessmentError(
                    f"Pro tuto událost již existuje aktivní posouzení "
                    f"pro ohroženou skupinu „{group_name}“."
                )


hazard_library_template_assessment_service = HazardLibraryTemplateAssessmentService()
