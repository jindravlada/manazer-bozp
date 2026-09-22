from datetime import datetime

from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
    HazardLibraryTemplateExistingMeasure,
)
from moduly.rizeni_rizik.repository.hazard_library_template_existing_measure_exposed_group_repository import (
    HazardLibraryTemplateExistingMeasureExposedGroupRepository,
)
from moduly.rizeni_rizik.repository.hazard_library_template_measure_repository import (
    HazardLibraryTemplateExistingMeasureRepository,
)
from moduly.rizeni_rizik.sluzby.existing_measure_relevance import (
    apply_assessment_ref_changes,
    resolve_create_refs,
    validate_measure_refs,
)
from moduly.rizeni_rizik.sluzby.exposed_target_ref import ExposedTargetRef
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)


class HazardLibraryTemplateExistingMeasureError(ValueError):
    pass


def normalize_template_measure_description(description: str) -> str:
    return " ".join(description.strip().split()).casefold()


class HazardLibraryTemplateExistingMeasureService:
    def __init__(self):
        self.repository = HazardLibraryTemplateExistingMeasureRepository()
        self.relevance_repository = HazardLibraryTemplateExistingMeasureExposedGroupRepository()

    def get_for_assessment(
        self,
        template_assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateExistingMeasure]:
        return self.repository.get_for_assessment(
            template_assessment_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, measure_id: int | None) -> HazardLibraryTemplateExistingMeasure | None:
        if not measure_id:
            return None
        return self.repository.get_by_id(measure_id)

    def get_target_refs(self, measure_id: int) -> list[ExposedTargetRef]:
        return self.relevance_repository.list_refs(measure_id)

    def create_measure(
        self,
        *,
        template_id: int,
        template_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None = None,
    ) -> HazardLibraryTemplateExistingMeasure:
        normalized_description = description.strip()
        if not normalized_description:
            raise HazardLibraryTemplateExistingMeasureError("Popis opatření je povinný.")

        self._validate_assessment(template_id, template_assessment_id)
        self._validate_unique_active_description(
            template_assessment_id,
            description=normalized_description,
            exclude_measure_id=None,
            active=active,
        )
        refs = self._resolve_create_refs(template_assessment_id, target_refs)

        measure = HazardLibraryTemplateExistingMeasure(
            template_assessment_id=template_assessment_id,
            description=normalized_description,
            note=note.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(template_assessment_id),
        )
        saved = self.repository.add(measure)
        self.relevance_repository.replace_refs(saved.id, refs)
        return saved

    def update_measure(
        self,
        measure_id: int,
        *,
        template_id: int,
        template_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None = None,
    ) -> HazardLibraryTemplateExistingMeasure | None:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return None

        normalized_description = description.strip()
        if not normalized_description:
            raise HazardLibraryTemplateExistingMeasureError("Popis opatření je povinný.")

        self._validate_assessment(template_id, template_assessment_id)
        self._validate_unique_active_description(
            template_assessment_id,
            description=normalized_description,
            exclude_measure_id=measure_id,
            active=active,
        )
        refs = None
        if target_refs is not None:
            refs = self._validate_refs(template_assessment_id, target_refs)

        measure.template_assessment_id = template_assessment_id
        measure.description = normalized_description
        measure.note = note.strip()
        measure.active = active
        measure.updated_at = datetime.now()
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
        assessment_refs = hazard_library_template_assessment_service.get_target_refs(
            assessment_id,
        )
        try:
            return resolve_create_refs(target_refs, assessment_refs)
        except ValueError as error:
            raise HazardLibraryTemplateExistingMeasureError(str(error)) from error

    def _validate_refs(
        self,
        assessment_id: int,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
    ) -> list[ExposedTargetRef]:
        assessment_refs = hazard_library_template_assessment_service.get_target_refs(
            assessment_id,
        )
        try:
            return validate_measure_refs(target_refs, assessment_refs)
        except ValueError as error:
            raise HazardLibraryTemplateExistingMeasureError(str(error)) from error

    def activate_measure(self, measure_id: int) -> bool:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return False
        template_id = self._template_id_for_measure(measure)
        self._validate_unique_active_description(
            measure.template_assessment_id,
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
        template_id = self._template_id_for_measure(measure)
        measure.active = False
        measure.updated_at = datetime.now()
        self.repository.update(measure)
        return True

    def _template_id_for_measure(self, measure: HazardLibraryTemplateExistingMeasure) -> int:
        template_id = hazard_library_template_assessment_service.get_template_id_for_assessment(
            measure.template_assessment_id
        )
        if template_id is None:
            raise HazardLibraryTemplateExistingMeasureError("Posouzení vzoru neexistuje.")
        return template_id

    def _validate_assessment(self, template_id: int, template_assessment_id: int) -> None:
        assessment = hazard_library_template_assessment_service.get_by_id(template_assessment_id)
        if assessment is None:
            raise HazardLibraryTemplateExistingMeasureError("Posouzení vzoru neexistuje.")
        assessment_template_id = (
            hazard_library_template_assessment_service.get_template_id_for_assessment(
                assessment.id
            )
        )
        if assessment_template_id != template_id:
            raise HazardLibraryTemplateExistingMeasureError(
                "Posouzení nepatří do zvoleného vzoru."
            )

    def _validate_unique_active_description(
        self,
        template_assessment_id: int,
        *,
        description: str,
        exclude_measure_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        normalized = normalize_template_measure_description(description)
        for measure in self.get_for_assessment(template_assessment_id, include_inactive=True):
            if measure.id == exclude_measure_id:
                continue
            if not measure.active:
                continue
            if normalize_template_measure_description(measure.description) == normalized:
                raise HazardLibraryTemplateExistingMeasureError(
                    "U posouzení již existuje aktivní existující opatření se stejným popisem."
                )


hazard_library_template_existing_measure_service = HazardLibraryTemplateExistingMeasureService()
