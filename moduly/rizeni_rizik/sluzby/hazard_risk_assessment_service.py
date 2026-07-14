from dataclasses import dataclass
from datetime import datetime

from core.utils.czech_sort import czech_sorted
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_ASSESSMENT_STATUS,
    RISK_ASSESSMENT_STATUS_COMPLETED,
    RISK_ASSESSMENT_STATUSES,
    RISK_SEVERITIES,
    format_risk_assessment_status_label,
    format_risk_severity_label,
)
from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
from moduly.rizeni_rizik.repository.hazard_risk_assessment_repository import (
    HazardRiskAssessmentRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import (
    HazardEventRow,
    hazard_event_service,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    hazard_inventory_item_service,
)


class HazardRiskAssessmentError(ValueError):
    pass


def normalize_exposed_group(group: str) -> str:
    return " ".join(group.strip().split()).casefold()


@dataclass
class HazardRiskAssessmentRow:
    assessment: HazardRiskAssessment
    event_name: str
    inventory_item_name: str
    severity_label: str
    status_label: str


class HazardRiskAssessmentService:
    def __init__(self):
        self.repository = HazardRiskAssessmentRepository()

    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardRiskAssessmentRow]:
        assessments = self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=include_inactive,
        )
        event_rows = {
            row.event.id: row
            for row in hazard_event_service.get_for_identification(
                hazard_identification_id,
                include_inactive=True,
            )
        }
        rows = [self._to_row(assessment, event_rows) for assessment in assessments]
        return self._sort_rows(rows)

    def get_by_id(self, assessment_id: int | None) -> HazardRiskAssessment | None:
        if not assessment_id:
            return None
        return self.repository.get_by_id(assessment_id)

    def count_active_for_event(self, hazard_event_id: int) -> int:
        return self.repository.count_active_for_event(hazard_event_id)

    def count_active_by_events(self, hazard_identification_id: int) -> dict[int, int]:
        counts: dict[int, int] = {}
        for assessment in self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        ):
            counts[assessment.hazard_event_id] = counts.get(assessment.hazard_event_id, 0) + 1
        return counts

    def get_active_status_summary(self, hazard_identification_id: int) -> dict[str, int]:
        total = draft_count = completed_count = 0
        for assessment in self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        ):
            total += 1
            if assessment.assessment_status == RISK_ASSESSMENT_STATUS_COMPLETED:
                completed_count += 1
            else:
                draft_count += 1
        return {
            "total": total,
            "draft": draft_count,
            "completed": completed_count,
        }

    def get_event_candidates(self, hazard_identification_id: int) -> list[HazardEventRow]:
        return hazard_event_service.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        )

    def create_assessment(
        self,
        *,
        hazard_identification_id: int,
        hazard_event_id: int,
        exposed_group: str,
        consequence: str,
        severity: str,
        note: str = "",
        assessment_status: str = DEFAULT_RISK_ASSESSMENT_STATUS,
        conclusion: str = "",
        active: bool = True,
    ) -> HazardRiskAssessment:
        normalized_group = self._validate_exposed_group(exposed_group)
        normalized_consequence = self._validate_consequence(consequence)
        normalized_severity = self._validate_severity(severity)

        self._validate_event(hazard_identification_id, hazard_event_id)
        self._validate_unique_active_group(
            hazard_event_id,
            group=normalized_group,
            exclude_assessment_id=None,
            active=active,
        )

        assessment = HazardRiskAssessment(
            hazard_event_id=hazard_event_id,
            exposed_group=normalized_group,
            consequence=normalized_consequence,
            severity=normalized_severity,
            note=note.strip(),
            conclusion=conclusion.strip(),
            active=active,
        )
        self._apply_assessment_status(
            assessment,
            assessment_status=assessment_status,
            hazard_identification_id=hazard_identification_id,
            hazard_event_id=hazard_event_id,
            exposed_group=normalized_group,
            consequence=normalized_consequence,
            severity=normalized_severity,
        )
        return self.repository.add(assessment)

    def update_assessment(
        self,
        assessment_id: int,
        *,
        hazard_identification_id: int,
        hazard_event_id: int,
        exposed_group: str,
        consequence: str,
        severity: str,
        note: str = "",
        assessment_status: str = DEFAULT_RISK_ASSESSMENT_STATUS,
        conclusion: str = "",
        active: bool = True,
    ) -> HazardRiskAssessment | None:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return None

        normalized_group = self._validate_exposed_group(exposed_group)
        normalized_consequence = self._validate_consequence(consequence)
        normalized_severity = self._validate_severity(severity)

        self._validate_event(hazard_identification_id, hazard_event_id)
        self._validate_unique_active_group(
            hazard_event_id,
            group=normalized_group,
            exclude_assessment_id=assessment_id,
            active=active,
        )

        assessment.hazard_event_id = hazard_event_id
        assessment.exposed_group = normalized_group
        assessment.consequence = normalized_consequence
        assessment.severity = normalized_severity
        assessment.note = note.strip()
        assessment.conclusion = conclusion.strip()
        assessment.active = active
        self._apply_assessment_status(
            assessment,
            assessment_status=assessment_status,
            hazard_identification_id=hazard_identification_id,
            hazard_event_id=hazard_event_id,
            exposed_group=normalized_group,
            consequence=normalized_consequence,
            severity=normalized_severity,
        )
        assessment.updated_at = datetime.now()
        return self.repository.update(assessment)

    def activate_assessment(self, assessment_id: int) -> bool:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return False

        self._validate_unique_active_group(
            assessment.hazard_event_id,
            group=assessment.exposed_group,
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

    def _to_row(
        self,
        assessment: HazardRiskAssessment,
        event_rows: dict[int, HazardEventRow],
    ) -> HazardRiskAssessmentRow:
        event_row = event_rows.get(assessment.hazard_event_id)
        if event_row is None:
            return HazardRiskAssessmentRow(
                assessment=assessment,
                event_name="—",
                inventory_item_name="—",
                severity_label=format_risk_severity_label(assessment.severity),
                status_label=format_risk_assessment_status_label(assessment.assessment_status),
            )

        return HazardRiskAssessmentRow(
            assessment=assessment,
            event_name=event_row.event.name,
            inventory_item_name=event_row.inventory_item_name,
            severity_label=format_risk_severity_label(assessment.severity),
            status_label=format_risk_assessment_status_label(assessment.assessment_status),
        )

    def _sort_rows(self, rows: list[HazardRiskAssessmentRow]) -> list[HazardRiskAssessmentRow]:
        def sort_key(row: HazardRiskAssessmentRow) -> tuple:
            return (
                row.inventory_item_name.casefold(),
                row.event_name.casefold(),
                row.assessment.exposed_group.casefold(),
            )

        return czech_sorted(rows, key=sort_key)

    def _validate_exposed_group(self, exposed_group: str) -> str:
        normalized_group = exposed_group.strip()
        if not normalized_group:
            raise HazardRiskAssessmentError("Ohrožená skupina je povinná.")
        return normalized_group

    def _validate_consequence(self, consequence: str) -> str:
        normalized_consequence = consequence.strip()
        if not normalized_consequence:
            raise HazardRiskAssessmentError("Možný následek je povinný.")
        return normalized_consequence

    def _validate_severity(self, severity: str) -> str:
        if severity not in RISK_SEVERITIES:
            raise HazardRiskAssessmentError("Neplatná závažnost následku.")
        return severity

    def _apply_assessment_status(
        self,
        assessment: HazardRiskAssessment,
        *,
        assessment_status: str,
        hazard_identification_id: int,
        hazard_event_id: int,
        exposed_group: str,
        consequence: str,
        severity: str,
    ) -> None:
        if assessment_status not in RISK_ASSESSMENT_STATUSES:
            raise HazardRiskAssessmentError("Neplatný stav posouzení.")

        if assessment_status == RISK_ASSESSMENT_STATUS_COMPLETED:
            self._validate_event(hazard_identification_id, hazard_event_id)
            self._validate_exposed_group(exposed_group)
            self._validate_consequence(consequence)
            self._validate_severity(severity)
            assessment.completed_at = datetime.now()
        else:
            assessment.completed_at = None

        assessment.assessment_status = assessment_status

    def _validate_event(
        self,
        hazard_identification_id: int,
        hazard_event_id: int,
    ) -> None:
        event = hazard_event_service.get_by_id(hazard_event_id)
        if event is None:
            raise HazardRiskAssessmentError("Nežádoucí událost neexistuje.")

        item = hazard_inventory_item_service.get_by_id(event.inventory_item_id)
        if item is None:
            raise HazardRiskAssessmentError("Nežádoucí událost neexistuje.")
        if item.hazard_identification_id != hazard_identification_id:
            raise HazardRiskAssessmentError(
                "Nežádoucí událost musí patřit ke stejné identifikaci."
            )
        if not event.active:
            raise HazardRiskAssessmentError("Lze vybrat pouze aktivní nežádoucí událost.")

    def _validate_unique_active_group(
        self,
        hazard_event_id: int,
        *,
        group: str,
        exclude_assessment_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        normalized = normalize_exposed_group(group)
        for assessment in self.repository.get_for_event(hazard_event_id, include_inactive=True):
            if assessment.id == exclude_assessment_id:
                continue
            if not assessment.active:
                continue
            if normalize_exposed_group(assessment.exposed_group) == normalized:
                raise HazardRiskAssessmentError(
                    f"U vybrané nežádoucí události již existuje aktivní ohrožená skupina "
                    f"„{group.strip()}“."
                )


hazard_risk_assessment_service = HazardRiskAssessmentService()
