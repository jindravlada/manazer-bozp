from dataclasses import dataclass
from datetime import datetime

from core.utils.czech_sort import czech_sorted
from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
from moduly.rizeni_rizik.repository.hazard_risk_assessment_repository import (
    HazardRiskAssessmentRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import (
    HazardEventRow,
    hazard_event_service,
)
from moduly.rizeni_rizik.sluzby.identified_hazard_service import identified_hazard_service


class HazardRiskAssessmentError(ValueError):
    pass


def normalize_exposed_group(group: str) -> str:
    return " ".join(group.strip().split()).casefold()


@dataclass
class HazardRiskAssessmentRow:
    assessment: HazardRiskAssessment
    event_name: str
    hazard_name: str


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
        note: str = "",
        active: bool = True,
    ) -> HazardRiskAssessment:
        normalized_group = exposed_group.strip()
        if not normalized_group:
            raise HazardRiskAssessmentError("Ohrožená skupina je povinná.")

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
            note=note.strip(),
            active=active,
        )
        return self.repository.add(assessment)

    def update_assessment(
        self,
        assessment_id: int,
        *,
        hazard_identification_id: int,
        hazard_event_id: int,
        exposed_group: str,
        note: str = "",
        active: bool = True,
    ) -> HazardRiskAssessment | None:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return None

        normalized_group = exposed_group.strip()
        if not normalized_group:
            raise HazardRiskAssessmentError("Ohrožená skupina je povinná.")

        self._validate_event(hazard_identification_id, hazard_event_id)
        self._validate_unique_active_group(
            hazard_event_id,
            group=normalized_group,
            exclude_assessment_id=assessment_id,
            active=active,
        )

        assessment.hazard_event_id = hazard_event_id
        assessment.exposed_group = normalized_group
        assessment.note = note.strip()
        assessment.active = active
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
                hazard_name="—",
            )

        return HazardRiskAssessmentRow(
            assessment=assessment,
            event_name=event_row.event.name,
            hazard_name=event_row.hazard_name,
        )

    def _sort_rows(self, rows: list[HazardRiskAssessmentRow]) -> list[HazardRiskAssessmentRow]:
        def sort_key(row: HazardRiskAssessmentRow) -> tuple:
            return (
                row.event_name.casefold(),
                row.hazard_name.casefold(),
                row.assessment.exposed_group.casefold(),
            )

        return czech_sorted(rows, key=sort_key)

    def _validate_event(
        self,
        hazard_identification_id: int,
        hazard_event_id: int,
    ) -> None:
        event = hazard_event_service.get_by_id(hazard_event_id)
        if event is None:
            raise HazardRiskAssessmentError("Nežádoucí událost neexistuje.")

        hazard = identified_hazard_service.get_by_id(event.identified_hazard_id)
        if hazard is None:
            raise HazardRiskAssessmentError("Nežádoucí událost neexistuje.")
        if hazard.hazard_identification_id != hazard_identification_id:
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
