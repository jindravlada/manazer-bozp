from datetime import datetime

from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
from moduly.rizeni_rizik.repository.hazard_required_measure_repository import (
    HazardRequiredMeasureRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    hazard_inventory_item_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import hazard_risk_assessment_service


class HazardRequiredMeasureError(ValueError):
    pass


def normalize_required_measure_description(description: str) -> str:
    return " ".join(description.strip().split()).casefold()


class HazardRequiredMeasureService:
    def __init__(self):
        self.repository = HazardRequiredMeasureRepository()

    def get_for_assessment(
        self,
        hazard_risk_assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardRequiredMeasure]:
        return self.repository.get_for_assessment(
            hazard_risk_assessment_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, measure_id: int | None) -> HazardRequiredMeasure | None:
        if not measure_id:
            return None
        return self.repository.get_by_id(measure_id)

    def count_active_for_assessment(self, hazard_risk_assessment_id: int) -> int:
        return self.repository.count_active_for_assessment(hazard_risk_assessment_id)

    def count_active_by_assessments(self, hazard_identification_id: int) -> dict[int, int]:
        counts: dict[int, int] = {}
        for row in hazard_risk_assessment_service.get_for_identification(
            hazard_identification_id,
            include_inactive=True,
        ):
            assessment_id = row.assessment.id
            counts[assessment_id] = self.repository.count_active_for_assessment(assessment_id)
        return counts

    def create_measure(
        self,
        *,
        hazard_identification_id: int,
        hazard_risk_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> HazardRequiredMeasure:
        normalized_description = description.strip()
        if not normalized_description:
            raise HazardRequiredMeasureError("Popis opatření je povinný.")

        self._validate_assessment(hazard_identification_id, hazard_risk_assessment_id)
        self._validate_unique_active_description(
            hazard_risk_assessment_id,
            description=normalized_description,
            exclude_measure_id=None,
            active=active,
        )

        measure = HazardRequiredMeasure(
            hazard_risk_assessment_id=hazard_risk_assessment_id,
            description=normalized_description,
            note=note.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(hazard_risk_assessment_id),
        )
        return self.repository.add(measure)

    def update_measure(
        self,
        measure_id: int,
        *,
        hazard_identification_id: int,
        hazard_risk_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> HazardRequiredMeasure | None:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return None

        normalized_description = description.strip()
        if not normalized_description:
            raise HazardRequiredMeasureError("Popis opatření je povinný.")

        self._validate_assessment(hazard_identification_id, hazard_risk_assessment_id)
        self._validate_unique_active_description(
            hazard_risk_assessment_id,
            description=normalized_description,
            exclude_measure_id=measure_id,
            active=active,
        )

        measure.hazard_risk_assessment_id = hazard_risk_assessment_id
        measure.description = normalized_description
        measure.note = note.strip()
        measure.active = active
        measure.updated_at = datetime.now()
        return self.repository.update(measure)

    def activate_measure(self, measure_id: int) -> bool:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return False

        self._validate_unique_active_description(
            measure.hazard_risk_assessment_id,
            description=measure.description,
            exclude_measure_id=measure_id,
            active=True,
        )
        measure.active = True
        measure.updated_at = datetime.now()
        self.repository.update(measure)
        return True

    def deactivate_measure(self, measure_id: int) -> bool:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return False
        measure.active = False
        measure.updated_at = datetime.now()
        self.repository.update(measure)
        return True

    def _validate_assessment(
        self,
        hazard_identification_id: int,
        hazard_risk_assessment_id: int,
    ) -> None:
        assessment = hazard_risk_assessment_service.get_by_id(hazard_risk_assessment_id)
        if assessment is None:
            raise HazardRequiredMeasureError("Posouzení rizika neexistuje.")

        event = hazard_event_service.get_by_id(assessment.hazard_event_id)
        if event is None:
            raise HazardRequiredMeasureError("Posouzení rizika neexistuje.")

        item = hazard_inventory_item_service.get_by_id(event.inventory_item_id)
        if item is None:
            raise HazardRequiredMeasureError("Posouzení rizika neexistuje.")
        if item.hazard_identification_id != hazard_identification_id:
            raise HazardRequiredMeasureError(
                "Posouzení rizika musí patřit ke stejné identifikaci."
            )

    def _validate_unique_active_description(
        self,
        hazard_risk_assessment_id: int,
        *,
        description: str,
        exclude_measure_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        normalized = normalize_required_measure_description(description)
        for measure in self.repository.get_for_assessment(
            hazard_risk_assessment_id,
            include_inactive=True,
        ):
            if measure.id == exclude_measure_id:
                continue
            if not measure.active:
                continue
            if normalize_required_measure_description(measure.description) == normalized:
                raise HazardRequiredMeasureError(
                    f"U vybraného posouzení již existuje aktivní potřebné opatření "
                    f"s popisem „{description.strip()}“."
                )


hazard_required_measure_service = HazardRequiredMeasureService()
