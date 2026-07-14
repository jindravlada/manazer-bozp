from dataclasses import dataclass
from datetime import datetime

from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORY_LABELS,
    HAZARD_INVENTORY_RELATION_TYPE_LABELS,
    HAZARD_INVENTORY_RELATION_TYPES,
    inventory_relation_target_category,
)
from moduly.rizeni_rizik.modely.hazard_inventory_relation import HazardInventoryRelation
from moduly.rizeni_rizik.repository.hazard_inventory_relation_repository import (
    HazardInventoryRelationRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import hazard_inventory_item_service


class HazardInventoryRelationError(ValueError):
    pass


@dataclass
class HazardInventoryRelationRow:
    relation: HazardInventoryRelation
    target_name: str
    target_category: str
    target_category_label: str
    relation_type_label: str


class HazardInventoryRelationService:
    def __init__(self):
        self.repository = HazardInventoryRelationRepository()

    def get_for_source_item(
        self,
        source_item_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardInventoryRelationRow]:
        relations = self.repository.get_for_source_item(
            source_item_id,
            include_inactive=include_inactive,
        )
        return [self._to_row(relation) for relation in relations]

    def get_by_id(self, relation_id: int | None) -> HazardInventoryRelation | None:
        if not relation_id:
            return None
        return self.repository.get_by_id(relation_id)

    def count_active_for_source(self, source_item_id: int) -> int:
        return self.repository.count_active_for_source(source_item_id)

    def count_active_by_source_items(self, hazard_identification_id: int) -> dict[int, int]:
        counts: dict[int, int] = {}
        for relation in self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        ):
            counts[relation.source_item_id] = counts.get(relation.source_item_id, 0) + 1
        return counts

    def get_target_candidates(
        self,
        *,
        hazard_identification_id: int,
        source_item_id: int,
        relation_type: str,
    ) -> list:
        target_category = inventory_relation_target_category(relation_type)
        if target_category is None:
            return []
        items = hazard_inventory_item_service.get_by_category(
            hazard_identification_id,
            target_category,
            include_inactive=False,
        )
        return [item for item in items if item.id != source_item_id]

    def create_relation(
        self,
        *,
        hazard_identification_id: int,
        source_item_id: int,
        target_item_id: int,
        relation_type: str,
        note: str = "",
        active: bool = True,
    ) -> HazardInventoryRelation:
        self._validate_relation_type(relation_type)
        self._validate_relation(
            hazard_identification_id=hazard_identification_id,
            source_item_id=source_item_id,
            target_item_id=target_item_id,
            relation_type=relation_type,
            exclude_relation_id=None,
            active=active,
        )

        relation = HazardInventoryRelation(
            hazard_identification_id=hazard_identification_id,
            source_item_id=source_item_id,
            target_item_id=target_item_id,
            relation_type=relation_type,
            note=note.strip(),
            active=active,
        )
        return self.repository.add(relation)

    def update_relation(
        self,
        relation_id: int,
        *,
        relation_type: str,
        target_item_id: int,
        note: str = "",
        active: bool = True,
    ) -> HazardInventoryRelation | None:
        relation = self.repository.get_by_id(relation_id)
        if relation is None:
            return None

        self._validate_relation_type(relation_type)
        self._validate_relation(
            hazard_identification_id=relation.hazard_identification_id,
            source_item_id=relation.source_item_id,
            target_item_id=target_item_id,
            relation_type=relation_type,
            exclude_relation_id=relation_id,
            active=active,
        )

        relation.relation_type = relation_type
        relation.target_item_id = target_item_id
        relation.note = note.strip()
        relation.active = active
        relation.updated_at = datetime.now()
        return self.repository.update(relation)

    def activate_relation(self, relation_id: int) -> bool:
        relation = self.repository.get_by_id(relation_id)
        if relation is None:
            return False
        self._validate_relation(
            hazard_identification_id=relation.hazard_identification_id,
            source_item_id=relation.source_item_id,
            target_item_id=relation.target_item_id,
            relation_type=relation.relation_type,
            exclude_relation_id=relation_id,
            active=True,
        )
        relation.active = True
        relation.updated_at = datetime.now()
        self.repository.update(relation)
        return True

    def deactivate_relation(self, relation_id: int) -> bool:
        relation = self.repository.get_by_id(relation_id)
        if relation is None:
            return False
        relation.active = False
        relation.updated_at = datetime.now()
        self.repository.update(relation)
        return True

    def _to_row(self, relation: HazardInventoryRelation) -> HazardInventoryRelationRow:
        target = hazard_inventory_item_service.get_by_id(relation.target_item_id)
        target_name = target.name if target else ""
        target_category = target.category if target else ""
        return HazardInventoryRelationRow(
            relation=relation,
            target_name=target_name,
            target_category=target_category,
            target_category_label=HAZARD_INVENTORY_CATEGORY_LABELS.get(target_category, target_category),
            relation_type_label=HAZARD_INVENTORY_RELATION_TYPE_LABELS.get(
                relation.relation_type,
                relation.relation_type,
            ),
        )

    def _validate_relation_type(self, relation_type: str) -> None:
        if relation_type not in HAZARD_INVENTORY_RELATION_TYPES:
            raise HazardInventoryRelationError("Neplatný typ souvislosti.")

    def _validate_relation(
        self,
        *,
        hazard_identification_id: int,
        source_item_id: int,
        target_item_id: int,
        relation_type: str,
        exclude_relation_id: int | None,
        active: bool,
    ) -> None:
        if source_item_id == target_item_id:
            raise HazardInventoryRelationError("Položka nemůže být ve vazbě sama na sebe.")

        source = hazard_inventory_item_service.get_by_id(source_item_id)
        target = hazard_inventory_item_service.get_by_id(target_item_id)
        if source is None or target is None:
            raise HazardInventoryRelationError("Zdrojová nebo cílová položka nebyla nalezena.")

        if source.hazard_identification_id != hazard_identification_id:
            raise HazardInventoryRelationError("Zdrojová položka nepatří k této identifikaci.")
        if target.hazard_identification_id != hazard_identification_id:
            raise HazardInventoryRelationError("Cílová položka nepatří k této identifikaci.")

        expected_category = inventory_relation_target_category(relation_type)
        if expected_category is None:
            raise HazardInventoryRelationError("Neplatný typ souvislosti.")
        if target.category != expected_category:
            label = HAZARD_INVENTORY_RELATION_TYPE_LABELS.get(relation_type, relation_type)
            raise HazardInventoryRelationError(
                f"Typ souvislosti „{label}“ vyžaduje položku jiné kategorie."
            )

        if not target.active:
            raise HazardInventoryRelationError("Cílová položka musí být aktivní.")

        if not active:
            return

        for existing in self.repository.get_for_source_item(source_item_id, include_inactive=True):
            if existing.id == exclude_relation_id:
                continue
            if not existing.active:
                continue
            if (
                existing.target_item_id == target_item_id
                and existing.relation_type == relation_type
            ):
                raise HazardInventoryRelationError(
                    "Aktivní souvislost se stejným typem a cílovou položkou již existuje."
                )


hazard_inventory_relation_service = HazardInventoryRelationService()
