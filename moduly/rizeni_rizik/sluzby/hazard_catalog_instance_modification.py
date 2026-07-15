"""Příznak lokální úpravy instancí převzatých z katalogu (R18c)."""

from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
from moduly.rizeni_rizik.repository.hazard_event_repository import HazardEventRepository
from moduly.rizeni_rizik.repository.hazard_inventory_item_repository import (
    HazardInventoryItemRepository,
)
from moduly.rizeni_rizik.repository.hazard_risk_assessment_repository import (
    HazardRiskAssessmentRepository,
)

_inventory_item_repository = HazardInventoryItemRepository()
_event_repository = HazardEventRepository()
_assessment_repository = HazardRiskAssessmentRepository()


def inventory_item_is_catalog_instance(inventory_item_id: int | None) -> bool:
    if not inventory_item_id:
        return False
    item = _inventory_item_repository.get_by_id(inventory_item_id)
    return item is not None and item.source_template_id is not None


def mark_event_modified_if_catalog_instance(event: HazardEvent) -> None:
    if inventory_item_is_catalog_instance(event.inventory_item_id):
        event.modified = True


def mark_assessment_modified_if_catalog_instance(assessment: HazardRiskAssessment) -> None:
    event = _event_repository.get_by_id(assessment.hazard_event_id)
    if event is not None and inventory_item_is_catalog_instance(event.inventory_item_id):
        assessment.modified = True


def mark_existing_measure_modified_if_catalog_instance(measure: HazardExistingMeasure) -> None:
    assessment = _assessment_repository.get_by_id(measure.hazard_risk_assessment_id)
    if assessment is None:
        return
    event = _event_repository.get_by_id(assessment.hazard_event_id)
    if event is not None and inventory_item_is_catalog_instance(event.inventory_item_id):
        measure.modified = True


def mark_required_measure_modified_if_catalog_instance(measure: HazardRequiredMeasure) -> None:
    assessment = _assessment_repository.get_by_id(measure.hazard_risk_assessment_id)
    if assessment is None:
        return
    event = _event_repository.get_by_id(assessment.hazard_event_id)
    if event is not None and inventory_item_is_catalog_instance(event.inventory_item_id):
        measure.modified = True
