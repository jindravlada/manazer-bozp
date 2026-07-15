"""Aktualizace lokální instance z novější verze Master zdroje (R18e)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_ASSESSMENT_STATUS,
    HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
)
from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_modification import (
    inventory_item_is_catalog_instance,
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


class HazardCatalogInstanceUpdateError(ValueError):
    pass


@dataclass(frozen=True)
class CatalogInstanceUpdateOffer:
    inventory_item_id: int
    item_name: str
    template_id: int
    template_name: str
    source_template_version: int
    master_version: int


@dataclass
class CatalogInstanceUpdateResult:
    item: HazardInventoryItem
    previous_version: int
    new_version: int
    event_count: int
    assessment_count: int
    existing_measure_count: int
    required_measure_count: int


class HazardCatalogInstanceUpdateService:
    def can_offer_update(
        self,
        *,
        hazard_identification_id: int | None,
        identification_status: str,
        read_only: bool,
    ) -> bool:
        if hazard_identification_id is None or read_only:
            return False
        return identification_status != HAZARD_IDENTIFICATION_STATUS_ARCHIVED

    def get_update_offer(self, inventory_item_id: int) -> CatalogInstanceUpdateOffer | None:
        item, template = self._load_item_and_template(inventory_item_id)
        if item.source_template_version is None or template.version_number is None:
            return None
        if template.version_number <= item.source_template_version:
            return None
        return CatalogInstanceUpdateOffer(
            inventory_item_id=item.id,
            item_name=item.name,
            template_id=template.id,
            template_name=template.name,
            source_template_version=item.source_template_version,
            master_version=template.version_number,
        )

    def update_from_master(self, inventory_item_id: int) -> CatalogInstanceUpdateResult:
        item, template = self._load_item_and_template(inventory_item_id)
        offer = self.get_update_offer(inventory_item_id)
        if offer is None:
            raise HazardCatalogInstanceUpdateError(
                "Lokální instance již odpovídá revizi Master zdroje nebo není k dispozici novější revize."
            )

        identification = hazard_identification_service.get_by_id(item.hazard_identification_id)
        if identification is None:
            raise HazardCatalogInstanceUpdateError("Identifikace neexistuje.")
        if identification.status == HAZARD_IDENTIFICATION_STATUS_ARCHIVED:
            raise HazardCatalogInstanceUpdateError(
                "U archivované identifikace nelze aktualizovat zdroj z Master katalogu."
            )
        if not template.active:
            raise HazardCatalogInstanceUpdateError(
                "Lze aktualizovat pouze z aktivního Master zdroje rizika."
            )

        try:
            hazard_inventory_item_service._validate_unique_active_name(
                item.hazard_identification_id,
                category=template.category,
                name=template.name.strip(),
                exclude_item_id=item.id,
                active=item.active,
            )
        except HazardInventoryItemError as error:
            raise HazardCatalogInstanceUpdateError(str(error)) from error

        events, event_assessments, assessment_measures = self._load_template_tree(template.id)
        previous_version = item.source_template_version or 0

        from core.database.session import get_session

        session = get_session()
        try:
            managed_item = session.get(HazardInventoryItem, item.id)
            if managed_item is None:
                raise HazardCatalogInstanceUpdateError("Položka analýzy neexistuje.")

            self._delete_inventory_item_tree(session, managed_item.id)
            counts = self._copy_template_tree_to_item(
                session,
                item=managed_item,
                events=events,
                event_assessments=event_assessments,
                assessment_measures=assessment_measures,
            )

            managed_item.category = template.category
            managed_item.name = template.name.strip()
            managed_item.description = template.description or ""
            managed_item.source_template_version = template.version_number
            managed_item.updated_at = datetime.now()

            session.commit()
            session.refresh(managed_item)
        except HazardCatalogInstanceUpdateError:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return CatalogInstanceUpdateResult(
            item=managed_item,
            previous_version=previous_version,
            new_version=template.version_number,
            event_count=counts[0],
            assessment_count=counts[1],
            existing_measure_count=counts[2],
            required_measure_count=counts[3],
        )

    def _load_item_and_template(self, inventory_item_id: int):
        item = hazard_inventory_item_service.get_by_id(inventory_item_id)
        if item is None:
            raise HazardCatalogInstanceUpdateError("Položka analýzy neexistuje.")
        if not inventory_item_is_catalog_instance(item.id):
            raise HazardCatalogInstanceUpdateError(
                "Aktualizace z Master je dostupná pouze u zdroje převzatého z katalogu."
            )
        if item.source_template_id is None:
            raise HazardCatalogInstanceUpdateError("Položka nemá evidovaný původ z katalogu.")

        template = hazard_library_template_service.get_by_id(item.source_template_id)
        if template is None:
            raise HazardCatalogInstanceUpdateError("Master zdroj rizika již neexistuje.")
        return item, template

    def _load_template_tree(self, template_id: int):
        events = [
            event
            for event in hazard_library_template_event_service.get_for_template(
                template_id,
                include_inactive=True,
            )
            if event.active
        ]

        event_assessments: dict[int, list] = {}
        for event in events:
            assessments = [
                assessment
                for assessment in hazard_library_template_assessment_service.repository.get_for_event(
                    event.id,
                    include_inactive=True,
                )
                if assessment.active
            ]
            for assessment in assessments:
                if assessment.exposed_group_id is None:
                    raise HazardCatalogInstanceUpdateError(
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
                    if measure.active
                ]
                required = [
                    measure
                    for measure in hazard_library_template_required_measure_service.get_for_assessment(
                        assessment.id,
                        include_inactive=True,
                    )
                    if measure.active
                ]
                assessment_measures[assessment.id] = (existing, required)

        return events, event_assessments, assessment_measures

    def _delete_inventory_item_tree(self, session, inventory_item_id: int) -> None:
        from sqlalchemy import delete, select

        event_ids = list(
            session.scalars(
                select(HazardEvent.id).where(HazardEvent.inventory_item_id == inventory_item_id)
            )
        )
        if not event_ids:
            return

        assessment_ids = list(
            session.scalars(
                select(HazardRiskAssessment.id).where(
                    HazardRiskAssessment.hazard_event_id.in_(event_ids)
                )
            )
        )
        if assessment_ids:
            session.execute(
                delete(HazardRequiredMeasure).where(
                    HazardRequiredMeasure.hazard_risk_assessment_id.in_(assessment_ids)
                )
            )
            session.execute(
                delete(HazardExistingMeasure).where(
                    HazardExistingMeasure.hazard_risk_assessment_id.in_(assessment_ids)
                )
            )
            session.execute(
                delete(HazardRiskAssessment).where(HazardRiskAssessment.id.in_(assessment_ids))
            )
        session.execute(
            delete(HazardEvent).where(HazardEvent.inventory_item_id == inventory_item_id)
        )

    def _copy_template_tree_to_item(
        self,
        session,
        *,
        item: HazardInventoryItem,
        events,
        event_assessments,
        assessment_measures,
    ) -> tuple[int, int, int, int]:
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
                active=True,
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
                    active=True,
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
                            active=True,
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
                            active=True,
                            modified=False,
                            sort_order=measure.sort_order,
                        )
                    )
                    required_measure_count += 1

        return event_count, assessment_count, existing_measure_count, required_measure_count


hazard_catalog_instance_update_service = HazardCatalogInstanceUpdateService()
