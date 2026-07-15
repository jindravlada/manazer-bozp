"""Převzetí zdroje rizika z katalogu do analýzy pracoviště (R18a)."""

from __future__ import annotations

from dataclasses import dataclass

from core.utils.czech_sort import czech_sorted
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_ASSESSMENT_STATUS,
    HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
)
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_SCOPE_ALL,
    HAZARD_LIBRARY_SCOPE_SELECTED,
)
from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
from moduly.rizeni_rizik.repository.hazard_library_template_repository import (
    HazardLibraryTemplateOperationRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    HazardInventoryItemError,
    hazard_inventory_item_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    hazard_library_template_event_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    hazard_library_template_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
    hazard_library_template_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
)


class HazardLibraryTemplateApplyError(ValueError):
    pass


@dataclass
class HazardLibraryTemplateApplyResult:
    item: HazardInventoryItem
    template: HazardLibraryTemplate
    event_count: int
    assessment_count: int
    existing_measure_count: int
    required_measure_count: int


@dataclass
class HazardLibraryTemplateCatalogGroups:
    recommended: list[HazardLibraryTemplate]
    other: list[HazardLibraryTemplate]


class HazardLibraryTemplateApplyService:
    def __init__(self):
        self.operation_repository = HazardLibraryTemplateOperationRepository()

    def can_apply_template(
        self,
        *,
        hazard_identification_id: int | None,
        identification_status: str,
    ) -> bool:
        if hazard_identification_id is None:
            return False
        return identification_status != HAZARD_IDENTIFICATION_STATUS_ARCHIVED

    def is_recommended_template(
        self,
        template: HazardLibraryTemplate,
        operation_id: int | None,
    ) -> bool:
        if not template.active:
            return False
        if template.application_scope == HAZARD_LIBRARY_SCOPE_ALL:
            return True
        if template.application_scope == HAZARD_LIBRARY_SCOPE_SELECTED:
            if operation_id is None:
                return False
            return self.operation_repository.has_link(template.id, operation_id)
        return False

    def get_template_groups(
        self,
        *,
        operation_id: int | None,
        category: str | None = None,
    ) -> HazardLibraryTemplateCatalogGroups:
        recommended: list[HazardLibraryTemplate] = []
        other: list[HazardLibraryTemplate] = []

        for template in hazard_library_template_service.repository.get_all(
            include_inactive=False,
        ):
            if category is not None and template.category != category:
                continue
            if self.is_recommended_template(template, operation_id):
                recommended.append(template)
            else:
                other.append(template)

        sort_key = lambda template: template.name.casefold()  # noqa: E731
        return HazardLibraryTemplateCatalogGroups(
            recommended=czech_sorted(recommended, key=sort_key),
            other=czech_sorted(other, key=sort_key),
        )

    def apply_template(
        self,
        *,
        hazard_identification_id: int,
        template_id: int,
        include_inactive: bool = False,
    ) -> HazardLibraryTemplateApplyResult:
        identification = hazard_identification_service.get_by_id(hazard_identification_id)
        if identification is None:
            raise HazardLibraryTemplateApplyError("Identifikace neexistuje.")
        if identification.status == HAZARD_IDENTIFICATION_STATUS_ARCHIVED:
            raise HazardLibraryTemplateApplyError(
                "U archivované identifikace nelze převzít zdroj z katalogu."
            )

        template = hazard_library_template_service.get_by_id(template_id)
        if template is None:
            raise HazardLibraryTemplateApplyError("Zdroj rizika neexistuje.")
        if not template.active:
            raise HazardLibraryTemplateApplyError(
                "Lze převzít pouze aktivní zdroj rizika z katalogu."
            )

        try:
            hazard_inventory_item_service._validate_category(template.category)
            hazard_inventory_item_service._validate_unique_active_name(
                hazard_identification_id,
                category=template.category,
                name=template.name,
                exclude_item_id=None,
                active=True,
            )
        except HazardInventoryItemError as error:
            raise HazardLibraryTemplateApplyError(str(error)) from error

        events = [
            event
            for event in hazard_library_template_event_service.get_for_template(
                template_id,
                include_inactive=True,
            )
            if include_inactive or event.active
        ]

        event_assessments: dict[int, list] = {}
        for event in events:
            assessments = [
                assessment
                for assessment in hazard_library_template_assessment_service.repository.get_for_event(
                    event.id,
                    include_inactive=True,
                )
                if include_inactive or assessment.active
            ]
            for assessment in assessments:
                if assessment.exposed_group_id is None:
                    raise HazardLibraryTemplateApplyError(
                        f"Posouzení události „{event.name}“ nemá přiřazenou ohroženou skupinu."
                    )
            event_assessments[event.id] = assessments

        assessment_measures: dict[int, tuple[list, list]] = {}
        for event in events:
            for assessment in event_assessments[event.id]:
                existing = [
                    measure
                    for measure in hazard_library_template_existing_measure_service.get_for_assessment(
                        assessment.id,
                        include_inactive=True,
                    )
                    if include_inactive or measure.active
                ]
                required = [
                    measure
                    for measure in hazard_library_template_required_measure_service.get_for_assessment(
                        assessment.id,
                        include_inactive=True,
                    )
                    if include_inactive or measure.active
                ]
                assessment_measures[assessment.id] = (existing, required)

        from core.database.session import get_session

        session = get_session()
        try:
            sort_order = hazard_inventory_item_service.repository.next_sort_order(
                hazard_identification_id,
                template.category,
            )
            item = HazardInventoryItem(
                hazard_identification_id=hazard_identification_id,
                category=template.category,
                name=template.name.strip(),
                description=template.description or "",
                active=True,
                sort_order=sort_order,
                source_template_id=template.id,
                source_template_version=template.version_number,
            )
            session.add(item)
            session.flush()

            event_count = 0
            assessment_count = 0
            existing_measure_count = 0
            required_measure_count = 0

            for event in events:
                hazard_event = HazardEvent(
                    inventory_item_id=item.id,
                    name=event.name,
                    description=event.description or "",
                    note=event.note or "",
                    active=event.active if include_inactive else True,
                    modified=False,
                    sort_order=event.sort_order,
                )
                session.add(hazard_event)
                session.flush()
                event_count += 1

                for assessment in event_assessments[event.id]:
                    group_ids = hazard_library_template_assessment_service.get_group_ids(
                        assessment.id,
                    )
                    if not group_ids and assessment.exposed_group_id:
                        group_ids = [assessment.exposed_group_id]
                    hazard_assessment = HazardRiskAssessment(
                        hazard_event_id=hazard_event.id,
                        exposed_group_id=group_ids[0] if group_ids else None,
                        exposed_group="",
                        severity=assessment.severity,
                        note=assessment.note or "",
                        conclusion=assessment.conclusion or "",
                        assessment_status=DEFAULT_RISK_ASSESSMENT_STATUS,
                        completed_at=None,
                        active=assessment.active if include_inactive else True,
                        modified=False,
                    )
                    session.add(hazard_assessment)
                    session.flush()
                    from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
                        HazardRiskAssessmentExposedGroup,
                    )

                    for sort_order, group_id in enumerate(group_ids, start=1):
                        session.add(
                            HazardRiskAssessmentExposedGroup(
                                assessment_id=hazard_assessment.id,
                                exposed_group_id=group_id,
                                sort_order=sort_order,
                            ),
                        )
                    assessment_count += 1

                    existing_measures, required_measures = assessment_measures[assessment.id]
                    for measure in existing_measures:
                        session.add(
                            HazardExistingMeasure(
                                hazard_risk_assessment_id=hazard_assessment.id,
                                description=measure.description,
                                note=measure.note or "",
                                active=measure.active if include_inactive else True,
                                modified=False,
                                sort_order=measure.sort_order,
                            )
                        )
                        existing_measure_count += 1
                    for measure in required_measures:
                        session.add(
                            HazardRequiredMeasure(
                                hazard_risk_assessment_id=hazard_assessment.id,
                                description=measure.description,
                                note=measure.note or "",
                                active=measure.active if include_inactive else True,
                                modified=False,
                                sort_order=measure.sort_order,
                            )
                        )
                        required_measure_count += 1

            session.commit()
            session.refresh(item)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return HazardLibraryTemplateApplyResult(
            item=item,
            template=template,
            event_count=event_count,
            assessment_count=assessment_count,
            existing_measure_count=existing_measure_count,
            required_measure_count=required_measure_count,
        )


hazard_library_template_apply_service = HazardLibraryTemplateApplyService()
