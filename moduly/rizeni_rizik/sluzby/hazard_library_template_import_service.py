"""Import položky analýzy pracoviště do katalogu zdrojů rizik (R17c, Master R17d)."""

from __future__ import annotations

from dataclasses import dataclass

from moduly.rizeni_rizik.constants import HAZARD_IDENTIFICATION_STATUS_ARCHIVED
from moduly.rizeni_rizik.constants_library import (
    DEFAULT_HAZARD_LIBRARY_SCOPE,
    DEFAULT_HAZARD_LIBRARY_VERSION,
    HAZARD_LIBRARY_REVISION_REASON_FROM_IDENTIFICATION,
    HAZARD_LIBRARY_SCOPE_SELECTED,
)
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
    HazardLibraryTemplateAssessment,
)
from moduly.rizeni_rizik.modely.hazard_library_template_event import HazardLibraryTemplateEvent
from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
    HazardLibraryTemplateExistingMeasure,
    HazardLibraryTemplateRequiredMeasure,
)
from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
    HazardLibraryTemplateOperation,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    hazard_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    hazard_inventory_item_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    HazardLibraryTemplateError,
    HazardLibraryTemplateService,
    hazard_library_template_service,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    hazard_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    hazard_risk_assessment_service,
)
from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    effective_target_refs,
    has_exposed_target_refs,
    legacy_exposed_group_id,
)


class HazardLibraryTemplateImportError(ValueError):
    pass


@dataclass
class HazardLibraryTemplateImportResult:
    template: HazardLibraryTemplate
    event_count: int
    assessment_count: int
    existing_measure_count: int
    required_measure_count: int


class HazardLibraryTemplateImportService:
    def __init__(self):
        self.template_service: HazardLibraryTemplateService = hazard_library_template_service

    def can_save_inventory_item(
        self,
        *,
        hazard_identification_id: int | None,
        identification_status: str,
        inventory_item_id: int | None,
    ) -> bool:
        if hazard_identification_id is None or inventory_item_id is None:
            return False
        if identification_status == HAZARD_IDENTIFICATION_STATUS_ARCHIVED:
            return False
        item = hazard_inventory_item_service.get_by_id(inventory_item_id)
        if item is None:
            return False
        if item.hazard_identification_id != hazard_identification_id:
            return False
        return bool(item.active)

    def import_inventory_item(
        self,
        *,
        hazard_identification_id: int,
        inventory_item_id: int,
        name: str,
        description: str = "",
        application_scope: str = DEFAULT_HAZARD_LIBRARY_SCOPE,
        note: str = "",
        operation_ids: list[int] | None = None,
        include_inactive: bool = False,
    ) -> HazardLibraryTemplateImportResult:
        identification = hazard_identification_service.get_by_id(hazard_identification_id)
        if identification is None:
            raise HazardLibraryTemplateImportError("Identifikace neexistuje.")
        if identification.status == HAZARD_IDENTIFICATION_STATUS_ARCHIVED:
            raise HazardLibraryTemplateImportError(
                "U archivované identifikace nelze ukládat položky do katalogu zdrojů rizik."
            )

        item = hazard_inventory_item_service.get_by_id(inventory_item_id)
        if item is None:
            raise HazardLibraryTemplateImportError("Položka analýzy neexistuje.")
        if item.hazard_identification_id != hazard_identification_id:
            raise HazardLibraryTemplateImportError(
                "Položka analýzy nepatří do zvolené identifikace."
            )
        if not item.active:
            raise HazardLibraryTemplateImportError(
                "Do katalogu lze uložit pouze aktivní položku analýzy."
            )

        try:
            normalized_name = self.template_service._validate_name(name)
            validated_category = self.template_service._validate_category(
                item.category,
                previous_code=item.category,
            )
            scope = self.template_service._validate_scope(application_scope)
            validated_operation_ids = self.template_service._validate_operation_ids(
                scope,
                operation_ids or [],
            )
            self.template_service._ensure_unique_active_name(normalized_name)
        except HazardLibraryTemplateError as error:
            raise HazardLibraryTemplateImportError(str(error)) from error

        events = [
            event
            for event in hazard_event_service.get_for_inventory_item(
                inventory_item_id,
                include_inactive=True,
            )
            if include_inactive or event.active
        ]
        event_assessments: dict[int, list] = {}
        for event in events:
            assessments = [
                assessment
                for assessment in hazard_risk_assessment_service.repository.get_for_event(
                    event.id,
                    include_inactive=True,
                )
                if include_inactive or assessment.active
            ]
            for assessment in assessments:
                if not has_exposed_target_refs(
                    hazard_risk_assessment_service.get_target_refs(assessment.id),
                    legacy_exposed_group_id=assessment.exposed_group_id,
                ):
                    raise HazardLibraryTemplateImportError(
                        f"Posouzení události „{event.name}“ nemá přiřazenou ohroženou skupinu."
                    )
            event_assessments[event.id] = assessments

        assessment_measures: dict[int, tuple[list, list]] = {}
        for event in events:
            for assessment in event_assessments[event.id]:
                existing = [
                    measure
                    for measure in hazard_existing_measure_service.get_for_assessment(
                        assessment.id,
                        include_inactive=True,
                    )
                    if include_inactive or measure.active
                ]
                required = [
                    measure
                    for measure in hazard_required_measure_service.get_for_assessment(
                        assessment.id,
                        include_inactive=True,
                    )
                    if include_inactive or measure.active
                ]
                assessment_measures[assessment.id] = (existing, required)

        from core.database.session import get_session

        session = get_session()
        try:
            template = HazardLibraryTemplate(
                name=normalized_name,
                category=validated_category,
                description=description.strip() or (item.description or ""),
                application_scope=scope,
                version_number=DEFAULT_HAZARD_LIBRARY_VERSION,
                note=note.strip(),
                active=True,
                source_identification_id=hazard_identification_id,
                source_inventory_item_id=inventory_item_id,
            )
            session.add(template)
            session.flush()

            if scope == HAZARD_LIBRARY_SCOPE_SELECTED:
                for operation_id in validated_operation_ids:
                    session.add(
                        HazardLibraryTemplateOperation(
                            template_id=template.id,
                            operation_id=operation_id,
                        )
                    )

            event_count = 0
            assessment_count = 0
            existing_measure_count = 0
            required_measure_count = 0

            for event in events:
                template_event = HazardLibraryTemplateEvent(
                    template_id=template.id,
                    name=event.name,
                    description=event.description or "",
                    note=event.note or "",
                    active=event.active if include_inactive else True,
                    sort_order=event.sort_order,
                )
                session.add(template_event)
                session.flush()
                event_count += 1

                for sort_index, assessment in enumerate(
                    event_assessments[event.id],
                    start=1,
                ):
                    target_refs = effective_target_refs(
                        hazard_risk_assessment_service.get_target_refs(assessment.id),
                        legacy_exposed_group_id=assessment.exposed_group_id,
                    )
                    template_assessment = HazardLibraryTemplateAssessment(
                        template_event_id=template_event.id,
                        exposed_group_id=legacy_exposed_group_id(target_refs),
                        severity=assessment.severity,
                        conclusion=assessment.conclusion or "",
                        note=assessment.note or "",
                        active=assessment.active if include_inactive else True,
                        sort_order=sort_index,
                    )
                    session.add(template_assessment)
                    session.flush()
                    from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
                        HazardLibraryTemplateAssessmentExposedGroup,
                    )

                    for group_sort, ref in enumerate(target_refs, start=1):
                        session.add(
                            HazardLibraryTemplateAssessmentExposedGroup(
                                assessment_id=template_assessment.id,
                                exposed_group_id=ref.source_id,
                                source_type=ref.source_type,
                                sort_order=group_sort,
                            ),
                        )
                    assessment_count += 1

                    existing_measures, required_measures = assessment_measures[assessment.id]
                    for measure in existing_measures:
                        session.add(
                            HazardLibraryTemplateExistingMeasure(
                                template_assessment_id=template_assessment.id,
                                description=measure.description,
                                note=measure.note or "",
                                active=measure.active if include_inactive else True,
                                sort_order=measure.sort_order,
                            )
                        )
                        existing_measure_count += 1
                    for measure in required_measures:
                        session.add(
                            HazardLibraryTemplateRequiredMeasure(
                                template_assessment_id=template_assessment.id,
                                description=measure.description,
                                note=measure.note or "",
                                active=measure.active if include_inactive else True,
                                sort_order=measure.sort_order,
                            )
                        )
                        required_measure_count += 1

            session.commit()
            session.refresh(template)
        except HazardLibraryTemplateError as error:
            session.rollback()
            raise HazardLibraryTemplateImportError(str(error)) from error
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        from moduly.rizeni_rizik.sluzby.hazard_library_template_revision_service import (
            hazard_library_template_revision_service,
        )

        hazard_library_template_revision_service.record_revision(
            template.id,
            revision_number=template.version_number,
            change_reason=HAZARD_LIBRARY_REVISION_REASON_FROM_IDENTIFICATION,
        )

        return HazardLibraryTemplateImportResult(
            template=template,
            event_count=event_count,
            assessment_count=assessment_count,
            existing_measure_count=existing_measure_count,
            required_measure_count=required_measure_count,
        )


hazard_library_template_import_service = HazardLibraryTemplateImportService()
