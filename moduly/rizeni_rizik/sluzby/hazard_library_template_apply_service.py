"""Převzetí zdroje rizika z katalogu do analýzy pracoviště (R18a)."""

from __future__ import annotations

from dataclasses import dataclass

from core.utils.czech_sort import czech_sorted
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_ASSESSMENT_STATUS,
    HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
)
from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
    HazardRiskAssessmentExposedGroup,
)
from moduly.rizeni_rizik.repository.hazard_library_template_repository import (
    HazardLibraryTemplateOperationRepository,
)
from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    effective_target_refs,
    has_exposed_target_refs,
    legacy_exposed_group_id,
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
        # R20e: katalog je obecný MASTER; doporučování dle rozsahu se nepoužívá.
        return False

    def get_applied_catalog_template_ids(
        self,
        *,
        hazard_identification_id: int,
        inventory_items: list[HazardInventoryItem] | None = None,
    ) -> set[int]:
        """ID katalogových zdrojů s aktivní instancí v identifikaci.

        ``inventory_items`` umožňuje zohlednit pracovní kopii identifikace
        (deferred-save), aniž by se četlo jen z DB.
        """
        if inventory_items is None:
            inventory_items = hazard_inventory_item_service.get_for_identification(
                hazard_identification_id,
                include_inactive=True,
            )
        return {
            item.source_template_id
            for item in inventory_items
            if item.active and item.source_template_id is not None
        }

    def get_template_groups(
        self,
        *,
        operation_id: int | None,
        category: str | None = None,
        hazard_identification_id: int | None = None,
        include_inactive: bool = False,
        applied_template_ids: set[int] | None = None,
        inventory_items: list[HazardInventoryItem] | None = None,
    ) -> HazardLibraryTemplateCatalogGroups:
        """Nabídka katalogu pro převzetí – vždy čerstvý dotaz do DB.

        Skryje zdroje, které už mají v identifikaci aktivní instanci
        (vazba ``source_template_id``). Parametry ``applied_template_ids`` /
        ``inventory_items`` připravují filtrování podle pracovní kopie.
        """
        if applied_template_ids is None and hazard_identification_id is not None:
            applied_template_ids = self.get_applied_catalog_template_ids(
                hazard_identification_id=hazard_identification_id,
                inventory_items=inventory_items,
            )
        elif applied_template_ids is None:
            applied_template_ids = set()

        templates: list[HazardLibraryTemplate] = []

        for template in hazard_library_template_service.repository.get_all(
            include_inactive=include_inactive,
        ):
            if category is not None and template.category != category:
                continue
            if not include_inactive and not template.active:
                continue
            if template.id in applied_template_ids:
                continue
            templates.append(template)

        sort_key = lambda template: template.name.casefold()  # noqa: E731
        return HazardLibraryTemplateCatalogGroups(
            recommended=[],
            other=czech_sorted(templates, key=sort_key),
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

        applied_ids = self.get_applied_catalog_template_ids(
            hazard_identification_id=hazard_identification_id,
        )
        if template.id in applied_ids:
            raise HazardLibraryTemplateApplyError(
                "Tento zdroj rizika z katalogu už je v identifikaci převzatý."
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
                if not has_exposed_target_refs(
                    hazard_library_template_assessment_service.get_target_refs(
                        assessment.id,
                    ),
                    legacy_exposed_group_id=assessment.exposed_group_id,
                ):
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
                    target_refs = effective_target_refs(
                        hazard_library_template_assessment_service.get_target_refs(
                            assessment.id,
                        ),
                        legacy_exposed_group_id=assessment.exposed_group_id,
                    )
                    hazard_assessment = HazardRiskAssessment(
                        hazard_event_id=hazard_event.id,
                        exposed_group_id=legacy_exposed_group_id(target_refs),
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

                    for sort_order, ref in enumerate(target_refs, start=1):
                        session.add(
                            HazardRiskAssessmentExposedGroup(
                                assessment_id=hazard_assessment.id,
                                exposed_group_id=ref.source_id,
                                source_type=ref.source_type,
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
