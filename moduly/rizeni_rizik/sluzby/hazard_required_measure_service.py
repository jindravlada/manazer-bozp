from datetime import datetime

from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
from moduly.rizeni_rizik.repository.hazard_required_measure_repository import (
    HazardRequiredMeasureRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_modification import (
    mark_required_measure_modified_if_catalog_instance,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    hazard_inventory_item_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import hazard_risk_assessment_service


class HazardRequiredMeasureError(ValueError):
    pass


def normalize_required_measure_title(title: str) -> str:
    return " ".join(title.strip().split()).casefold()


# Zpětná kompatibilita se starším názvem helperu.
normalize_required_measure_description = normalize_required_measure_title


def resolve_required_measure_fields(
    *,
    title: str | None = None,
    description: str | None = None,
    note: str | None = None,
) -> tuple[str, str]:
    """Vrátí (title, description) s ohledem na starší volání description=název, note=popis."""
    resolved_title = (title if title is not None else "").strip()
    resolved_description = (description if description is not None else "").strip()
    legacy_note = (note if note is not None else "").strip()

    if not resolved_title and resolved_description and not legacy_note:
        # Starší API: description = název, note chybí / prázdný.
        return resolved_description, ""
    if not resolved_title and resolved_description and legacy_note:
        # Starší API: description = název, note = popis.
        return resolved_description, legacy_note
    if resolved_title and not resolved_description and legacy_note:
        return resolved_title, legacy_note
    return resolved_title, resolved_description


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
        title: str | None = None,
        description: str | None = None,
        note: str | None = None,
        active: bool = True,
    ) -> HazardRequiredMeasure:
        resolved_title, resolved_description = resolve_required_measure_fields(
            title=title,
            description=description,
            note=note,
        )
        if not resolved_title:
            raise HazardRequiredMeasureError("Znění kontrolní otázky je povinné.")

        self._validate_assessment(hazard_identification_id, hazard_risk_assessment_id)
        self._validate_unique_active_title(
            hazard_risk_assessment_id,
            title=resolved_title,
            exclude_measure_id=None,
            active=active,
        )

        measure = HazardRequiredMeasure(
            hazard_risk_assessment_id=hazard_risk_assessment_id,
            title=resolved_title,
            description=resolved_title,
            note=resolved_description,
            active=active,
            sort_order=self.repository.next_sort_order(hazard_risk_assessment_id),
        )
        mark_required_measure_modified_if_catalog_instance(measure)
        return self.repository.add(measure)

    def update_measure(
        self,
        measure_id: int,
        *,
        hazard_identification_id: int,
        hazard_risk_assessment_id: int,
        title: str | None = None,
        description: str | None = None,
        note: str | None = None,
        active: bool = True,
    ) -> HazardRequiredMeasure | None:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return None

        resolved_title, resolved_description = resolve_required_measure_fields(
            title=title,
            description=description,
            note=note,
        )
        if not resolved_title:
            raise HazardRequiredMeasureError("Znění kontrolní otázky je povinné.")

        self._validate_assessment(hazard_identification_id, hazard_risk_assessment_id)
        self._validate_unique_active_title(
            hazard_risk_assessment_id,
            title=resolved_title,
            exclude_measure_id=measure_id,
            active=active,
        )

        measure.hazard_risk_assessment_id = hazard_risk_assessment_id
        measure.title = resolved_title
        measure.description = resolved_title
        measure.note = resolved_description
        measure.active = active
        measure.updated_at = datetime.now()
        mark_required_measure_modified_if_catalog_instance(measure)
        return self.repository.update(measure)

    def activate_measure(self, measure_id: int) -> bool:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return False

        self._validate_unique_active_title(
            measure.hazard_risk_assessment_id,
            title=measure.display_title(),
            exclude_measure_id=measure_id,
            active=True,
        )
        measure.active = True
        measure.updated_at = datetime.now()
        mark_required_measure_modified_if_catalog_instance(measure)
        self.repository.update(measure)
        return True

    def deactivate_measure(self, measure_id: int) -> bool:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return False
        measure.active = False
        measure.updated_at = datetime.now()
        mark_required_measure_modified_if_catalog_instance(measure)
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

    def _validate_unique_active_title(
        self,
        hazard_risk_assessment_id: int,
        *,
        title: str,
        exclude_measure_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        normalized = normalize_required_measure_title(title)
        for measure in self.repository.get_for_assessment(
            hazard_risk_assessment_id,
            include_inactive=True,
        ):
            if measure.id == exclude_measure_id:
                continue
            if not measure.active:
                continue
            if normalize_required_measure_title(measure.display_title()) == normalized:
                raise HazardRequiredMeasureError(
                    f"U vybraného posouzení již existuje aktivní kontrolní otázka "
                    f"s názvem „{title.strip()}“."
                )


hazard_required_measure_service = HazardRequiredMeasureService()
