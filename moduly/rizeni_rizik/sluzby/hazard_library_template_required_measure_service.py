from datetime import datetime

from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
    HazardLibraryTemplateRequiredMeasure,
)
from moduly.rizeni_rizik.repository.hazard_library_template_measure_repository import (
    HazardLibraryTemplateRequiredMeasureRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    normalize_template_measure_description,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_version import (
    bump_template_content_version,
)


class HazardLibraryTemplateRequiredMeasureError(ValueError):
    pass


class HazardLibraryTemplateRequiredMeasureService:
    def __init__(self):
        self.repository = HazardLibraryTemplateRequiredMeasureRepository()

    def get_for_assessment(
        self,
        template_assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateRequiredMeasure]:
        return self.repository.get_for_assessment(
            template_assessment_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, measure_id: int | None) -> HazardLibraryTemplateRequiredMeasure | None:
        if not measure_id:
            return None
        return self.repository.get_by_id(measure_id)

    def create_measure(
        self,
        *,
        template_id: int,
        template_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateRequiredMeasure:
        normalized_description = description.strip()
        if not normalized_description:
            raise HazardLibraryTemplateRequiredMeasureError("Popis opatření je povinný.")

        self._validate_assessment(template_id, template_assessment_id)
        self._validate_unique_active_description(
            template_assessment_id,
            description=normalized_description,
            exclude_measure_id=None,
            active=active,
        )

        measure = HazardLibraryTemplateRequiredMeasure(
            template_assessment_id=template_assessment_id,
            description=normalized_description,
            note=note.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(template_assessment_id),
        )
        saved = self.repository.add(measure)
        bump_template_content_version(template_id)
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
    ) -> HazardLibraryTemplateRequiredMeasure | None:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return None

        normalized_description = description.strip()
        if not normalized_description:
            raise HazardLibraryTemplateRequiredMeasureError("Popis opatření je povinný.")

        self._validate_assessment(template_id, template_assessment_id)
        self._validate_unique_active_description(
            template_assessment_id,
            description=normalized_description,
            exclude_measure_id=measure_id,
            active=active,
        )

        measure.template_assessment_id = template_assessment_id
        measure.description = normalized_description
        measure.note = note.strip()
        measure.active = active
        measure.updated_at = datetime.now()
        saved = self.repository.update(measure)
        bump_template_content_version(template_id)
        return saved

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
        bump_template_content_version(template_id)
        return True

    def deactivate_measure(self, measure_id: int) -> bool:
        measure = self.repository.get_by_id(measure_id)
        if measure is None:
            return False
        template_id = self._template_id_for_measure(measure)
        measure.active = False
        measure.updated_at = datetime.now()
        self.repository.update(measure)
        bump_template_content_version(template_id)
        return True

    def _template_id_for_measure(self, measure: HazardLibraryTemplateRequiredMeasure) -> int:
        template_id = hazard_library_template_assessment_service.get_template_id_for_assessment(
            measure.template_assessment_id
        )
        if template_id is None:
            raise HazardLibraryTemplateRequiredMeasureError("Posouzení vzoru neexistuje.")
        return template_id

    def _validate_assessment(self, template_id: int, template_assessment_id: int) -> None:
        assessment = hazard_library_template_assessment_service.get_by_id(template_assessment_id)
        if assessment is None:
            raise HazardLibraryTemplateRequiredMeasureError("Posouzení vzoru neexistuje.")
        assessment_template_id = (
            hazard_library_template_assessment_service.get_template_id_for_assessment(
                assessment.id
            )
        )
        if assessment_template_id != template_id:
            raise HazardLibraryTemplateRequiredMeasureError(
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
                raise HazardLibraryTemplateRequiredMeasureError(
                    "U posouzení již existuje aktivní potřebné opatření se stejným popisem."
                )


hazard_library_template_required_measure_service = HazardLibraryTemplateRequiredMeasureService()
