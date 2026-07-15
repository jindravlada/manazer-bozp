from dataclasses import dataclass
from datetime import datetime

from core.utils.czech_sort import czech_sorted
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_ASSESSMENT_STATUS,
    RISK_ASSESSMENT_STATUS_COMPLETED,
    RISK_ASSESSMENT_STATUSES,
    RISK_SEVERITIES,
    format_risk_assessment_status_label,
    format_risk_severity_label,
)
from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
from moduly.rizeni_rizik.repository.hazard_risk_assessment_exposed_group_repository import (
    HazardRiskAssessmentExposedGroupRepository,
)
from moduly.rizeni_rizik.repository.hazard_risk_assessment_repository import (
    HazardRiskAssessmentRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_modification import (
    mark_assessment_modified_if_catalog_instance,
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
    exposed_group_name: str
    severity_label: str
    status_label: str
    exposed_group_ids: tuple[int, ...] = ()


class HazardRiskAssessmentService:
    def __init__(self):
        self.repository = HazardRiskAssessmentRepository()
        self.group_repository = HazardRiskAssessmentExposedGroupRepository()

    def get_group_ids(self, assessment_id: int) -> list[int]:
        return self.group_repository.list_group_ids(assessment_id)

    def get_exposed_group_display_name(self, assessment: HazardRiskAssessment) -> str:
        group_ids = self.group_repository.list_group_ids(assessment.id)
        if not group_ids and assessment.exposed_group_id:
            group_ids = [assessment.exposed_group_id]
        names = [
            exposed_group_service.display_name(group_id) or f"#{group_id}"
            for group_id in group_ids
        ]
        if names:
            return ", ".join(names)
        if assessment.exposed_group:
            return assessment.exposed_group
        return "—"

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
        exposed_group_ids: list[int] | tuple[int, ...] | None = None,
        exposed_group_id: int | None = None,
        severity: str,
        note: str = "",
        assessment_status: str = DEFAULT_RISK_ASSESSMENT_STATUS,
        conclusion: str = "",
        active: bool = True,
    ) -> HazardRiskAssessment:
        validated_group_ids = self._validate_exposed_group_ids(
            exposed_group_ids,
            legacy_single_id=exposed_group_id,
        )
        normalized_severity = self._validate_severity(severity)

        self._validate_event(hazard_identification_id, hazard_event_id)
        self._validate_unique_active_groups(
            hazard_event_id,
            exposed_group_ids=validated_group_ids,
            exclude_assessment_id=None,
            active=active,
        )

        assessment = HazardRiskAssessment(
            hazard_event_id=hazard_event_id,
            exposed_group_id=validated_group_ids[0],
            exposed_group="",
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
            exposed_group_ids=validated_group_ids,
            severity=normalized_severity,
        )
        mark_assessment_modified_if_catalog_instance(assessment)
        saved = self.repository.add(assessment)
        self.group_repository.replace_groups(saved.id, validated_group_ids)
        return saved

    def update_assessment(
        self,
        assessment_id: int,
        *,
        hazard_identification_id: int,
        hazard_event_id: int,
        exposed_group_ids: list[int] | tuple[int, ...] | None = None,
        exposed_group_id: int | None = None,
        severity: str,
        note: str = "",
        assessment_status: str = DEFAULT_RISK_ASSESSMENT_STATUS,
        conclusion: str = "",
        active: bool = True,
    ) -> HazardRiskAssessment | None:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return None

        validated_group_ids = self._validate_exposed_group_ids(
            exposed_group_ids,
            legacy_single_id=exposed_group_id,
        )
        normalized_severity = self._validate_severity(severity)

        self._validate_event(hazard_identification_id, hazard_event_id)
        self._validate_unique_active_groups(
            hazard_event_id,
            exposed_group_ids=validated_group_ids,
            exclude_assessment_id=assessment_id,
            active=active,
        )

        assessment.hazard_event_id = hazard_event_id
        assessment.exposed_group_id = validated_group_ids[0]
        assessment.severity = normalized_severity
        assessment.note = note.strip()
        assessment.conclusion = conclusion.strip()
        assessment.active = active
        self._apply_assessment_status(
            assessment,
            assessment_status=assessment_status,
            hazard_identification_id=hazard_identification_id,
            hazard_event_id=hazard_event_id,
            exposed_group_ids=validated_group_ids,
            severity=normalized_severity,
        )
        assessment.updated_at = datetime.now()
        mark_assessment_modified_if_catalog_instance(assessment)
        saved = self.repository.update(assessment)
        self.group_repository.replace_groups(saved.id, validated_group_ids)
        return saved

    def activate_assessment(self, assessment_id: int) -> bool:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return False
        group_ids = self.group_repository.list_group_ids(assessment_id)
        if not group_ids and assessment.exposed_group_id:
            group_ids = [assessment.exposed_group_id]
        if not group_ids:
            raise HazardRiskAssessmentError("Posouzení nemá přiřazenou ohroženou skupinu.")

        self._validate_unique_active_groups(
            assessment.hazard_event_id,
            exposed_group_ids=group_ids,
            exclude_assessment_id=assessment_id,
            active=True,
        )
        assessment.active = True
        assessment.updated_at = datetime.now()
        mark_assessment_modified_if_catalog_instance(assessment)
        self.repository.update(assessment)
        return True

    def deactivate_assessment(self, assessment_id: int) -> bool:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return False
        assessment.active = False
        assessment.updated_at = datetime.now()
        mark_assessment_modified_if_catalog_instance(assessment)
        self.repository.update(assessment)
        return True

    def _to_row(
        self,
        assessment: HazardRiskAssessment,
        event_rows: dict[int, HazardEventRow],
    ) -> HazardRiskAssessmentRow:
        group_ids = tuple(self.group_repository.list_group_ids(assessment.id))
        if not group_ids and assessment.exposed_group_id:
            group_ids = (assessment.exposed_group_id,)
        exposed_group_name = self.get_exposed_group_display_name(assessment)
        event_row = event_rows.get(assessment.hazard_event_id)
        if event_row is None:
            return HazardRiskAssessmentRow(
                assessment=assessment,
                event_name="—",
                inventory_item_name="—",
                exposed_group_name=exposed_group_name,
                severity_label=format_risk_severity_label(assessment.severity),
                status_label=format_risk_assessment_status_label(assessment.assessment_status),
                exposed_group_ids=group_ids,
            )

        return HazardRiskAssessmentRow(
            assessment=assessment,
            event_name=event_row.event.name,
            inventory_item_name=event_row.inventory_item_name,
            exposed_group_name=exposed_group_name,
            severity_label=format_risk_severity_label(assessment.severity),
            status_label=format_risk_assessment_status_label(assessment.assessment_status),
            exposed_group_ids=group_ids,
        )

    def _sort_rows(self, rows: list[HazardRiskAssessmentRow]) -> list[HazardRiskAssessmentRow]:
        def sort_key(row: HazardRiskAssessmentRow) -> tuple:
            return (
                row.inventory_item_name.casefold(),
                row.event_name.casefold(),
                row.exposed_group_name.casefold(),
            )

        return czech_sorted(rows, key=sort_key)

    def _validate_exposed_group_ids(
        self,
        exposed_group_ids: list[int] | tuple[int, ...] | None,
        *,
        legacy_single_id: int | None,
    ) -> list[int]:
        values = list(exposed_group_ids or [])
        if not values and legacy_single_id is not None:
            values = [legacy_single_id]
        if not values:
            raise HazardRiskAssessmentError("Vyberte alespoň jednu ohroženou skupinu.")

        validated: list[int] = []
        seen: set[int] = set()
        for group_id in values:
            if group_id in seen:
                continue
            group = exposed_group_service.get_by_id(group_id)
            if group is None:
                raise HazardRiskAssessmentError("Vybraná ohrožená skupina neexistuje.")
            if not group.active:
                raise HazardRiskAssessmentError(
                    "Lze vybrat pouze aktivní ohroženou skupinu z číselníku."
                )
            seen.add(group.id)
            validated.append(group.id)
        return validated

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
        exposed_group_ids: list[int],
        severity: str,
    ) -> None:
        if assessment_status not in RISK_ASSESSMENT_STATUSES:
            raise HazardRiskAssessmentError("Neplatný stav posouzení.")

        if assessment_status == RISK_ASSESSMENT_STATUS_COMPLETED:
            self._validate_event(hazard_identification_id, hazard_event_id)
            self._validate_exposed_group_ids(exposed_group_ids, legacy_single_id=None)
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

    def _validate_unique_active_groups(
        self,
        hazard_event_id: int,
        *,
        exposed_group_ids: list[int],
        exclude_assessment_id: int | None,
        active: bool,
    ) -> None:
        if not active or not exposed_group_ids:
            return

        for assessment in self.repository.get_for_event(hazard_event_id, include_inactive=True):
            if assessment.id == exclude_assessment_id:
                continue
            if not assessment.active:
                continue
            other_ids = set(self.group_repository.list_group_ids(assessment.id))
            if not other_ids and assessment.exposed_group_id:
                other_ids = {assessment.exposed_group_id}
            overlap = set(exposed_group_ids) & other_ids
            if not overlap:
                continue
            group_name = exposed_group_service.display_name(next(iter(overlap))) or "—"
            raise HazardRiskAssessmentError(
                f"U vybrané nežádoucí události již existuje aktivní ohrožená skupina "
                f"„{group_name}“."
            )


hazard_risk_assessment_service = HazardRiskAssessmentService()
