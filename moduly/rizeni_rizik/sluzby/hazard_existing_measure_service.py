from datetime import datetime

from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
from moduly.rizeni_rizik.repository.hazard_existing_measure_exposed_group_repository import (
    HazardExistingMeasureExposedGroupRepository,
)
from moduly.rizeni_rizik.repository.hazard_existing_measure_repository import (
    HazardExistingMeasureRepository,
)
from moduly.rizeni_rizik.sluzby.existing_measure_relevance import (
    apply_assessment_ref_changes,
    resolve_create_refs,
    validate_measure_refs,
)
from moduly.rizeni_rizik.sluzby.exposed_target_ref import ExposedTargetRef
from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_modification import (
    mark_existing_measure_modified_if_catalog_instance,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    hazard_inventory_item_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import hazard_risk_assessment_service


class HazardExistingMeasureError(ValueError):
    pass


def normalize_measure_description(description: str) -> str:
    return " ".join(description.strip().split()).casefold()


class HazardExistingMeasureService:
    def __init__(self):
        self.repository = HazardExistingMeasureRepository()
        self.relevance_repository = HazardExistingMeasureExposedGroupRepository()

    def get_for_assessment(
        self,
        hazard_risk_assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardExistingMeasure]:
        return self.repository.get_for_assessment(
            hazard_risk_assessment_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, measure_id: int | None) -> HazardExistingMeasure | None:
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

    def get_target_refs(self, measure_id: int) -> list[ExposedTargetRef]:
        return self.relevance_repository.list_refs(measure_id)

    def create_measure(
        self,
        *,
        hazard_identification_id: int,
        hazard_risk_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None = None,
    ) -> HazardExistingMeasure:
        normalized_description = description.strip()
        if not normalized_description:
            raise HazardExistingMeasureError("Popis opatření je povinný.")

        self._validate_assessment(hazard_identification_id, hazard_risk_assessment_id)
        self._validate_unique_active_description(
            hazard_risk_assessment_id,
            description=normalized_description,
            exclude_measure_id=None,
            active=active,
        )
        refs = self._resolve_create_refs(hazard_risk_assessment_id, target_refs)

        measure = HazardExistingMeasure(
            hazard_risk_assessment_id=hazard_risk_assessment_id,
            description=normalized_description,
            note=note.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(hazard_risk_assessment_id),
        )
        mark_existing_measure_modified_if_catalog_instance(measure)
        saved = self.repository.add(measure)
        self.relevance_repository.replace_refs(saved.id, refs)
        return saved

    def update_measure(
        self,
        measure_id: int,
        *,
        hazard_identification_id: int,
        hazard_risk_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None = None,
    ) -> HazardExistingMeasure | None:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return None

        normalized_description = description.strip()
        if not normalized_description:
            raise HazardExistingMeasureError("Popis opatření je povinný.")

        self._validate_assessment(hazard_identification_id, hazard_risk_assessment_id)
        self._validate_unique_active_description(
            hazard_risk_assessment_id,
            description=normalized_description,
            exclude_measure_id=measure_id,
            active=active,
        )
        refs = None
        if target_refs is not None:
            refs = self._validate_refs(hazard_risk_assessment_id, target_refs)

        measure.hazard_risk_assessment_id = hazard_risk_assessment_id
        measure.description = normalized_description
        measure.note = note.strip()
        measure.active = active
        measure.updated_at = datetime.now()
        mark_existing_measure_modified_if_catalog_instance(measure)
        saved = self.repository.update(measure)
        if refs is not None:
            self.relevance_repository.replace_refs(saved.id, refs)
        return saved

    def sync_relevance_for_assessment(
        self,
        assessment_id: int,
        *,
        old_refs: list[ExposedTargetRef],
        new_refs: list[ExposedTargetRef],
    ) -> None:
        measures = self.repository.get_for_assessment(assessment_id, include_inactive=True)
        refs_by_id = self.relevance_repository.list_refs_for_measures(
            [measure.id for measure in measures],
        )
        for measure in measures:
            updated = apply_assessment_ref_changes(
                refs_by_id.get(measure.id, []),
                old_assessment_refs=old_refs,
                new_assessment_refs=new_refs,
            )
            self.relevance_repository.replace_refs(measure.id, updated)

    def _resolve_create_refs(
        self,
        assessment_id: int,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
    ) -> list[ExposedTargetRef]:
        assessment_refs = hazard_risk_assessment_service.get_target_refs(assessment_id)
        try:
            return resolve_create_refs(target_refs, assessment_refs)
        except ValueError as error:
            raise HazardExistingMeasureError(str(error)) from error

    def _validate_refs(
        self,
        assessment_id: int,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
    ) -> list[ExposedTargetRef]:
        assessment_refs = hazard_risk_assessment_service.get_target_refs(assessment_id)
        try:
            return validate_measure_refs(target_refs, assessment_refs)
        except ValueError as error:
            raise HazardExistingMeasureError(str(error)) from error

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
        mark_existing_measure_modified_if_catalog_instance(measure)
        self.repository.update(measure)
        return True

    def deactivate_measure(self, measure_id: int) -> bool:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return False
        measure.active = False
        measure.updated_at = datetime.now()
        mark_existing_measure_modified_if_catalog_instance(measure)
        self.repository.update(measure)
        return True

    def _validate_assessment(
        self,
        hazard_identification_id: int,
        hazard_risk_assessment_id: int,
    ) -> None:
        assessment = hazard_risk_assessment_service.get_by_id(hazard_risk_assessment_id)
        if assessment is None:
            raise HazardExistingMeasureError("Posouzení rizika neexistuje.")

        event = hazard_event_service.get_by_id(assessment.hazard_event_id)
        if event is None:
            raise HazardExistingMeasureError("Posouzení rizika neexistuje.")

        item = hazard_inventory_item_service.get_by_id(event.inventory_item_id)
        if item is None:
            raise HazardExistingMeasureError("Posouzení rizika neexistuje.")
        if item.hazard_identification_id != hazard_identification_id:
            raise HazardExistingMeasureError(
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

        normalized = normalize_measure_description(description)
        for measure in self.repository.get_for_assessment(
            hazard_risk_assessment_id,
            include_inactive=True,
        ):
            if measure.id == exclude_measure_id:
                continue
            if not measure.active:
                continue
            if normalize_measure_description(measure.description) == normalized:
                raise HazardExistingMeasureError(
                    f"U vybraného posouzení již existuje aktivní opatření "
                    f"s popisem „{description.strip()}“."
                )


hazard_existing_measure_service = HazardExistingMeasureService()
