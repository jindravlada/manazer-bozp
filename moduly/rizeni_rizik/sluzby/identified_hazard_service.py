from dataclasses import dataclass
from datetime import datetime

from core.utils.czech_sort import czech_sorted
from moduly.rizeni_rizik.constants import (
    DEFAULT_IDENTIFIED_HAZARD_SOURCE,
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
    IDENTIFIED_HAZARD_SOURCE_LABELS,
    IDENTIFIED_HAZARD_SOURCE_TYPES,
)
from moduly.rizeni_rizik.modely.identified_hazard import IdentifiedHazard
from moduly.rizeni_rizik.repository.identified_hazard_repository import (
    IdentifiedHazardRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import hazard_inventory_item_service


class IdentifiedHazardError(ValueError):
    pass


def normalize_hazard_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


@dataclass
class IdentifiedHazardRow:
    hazard: IdentifiedHazard
    inventory_item_name: str
    inventory_item_category: str
    inventory_item_category_label: str
    source_type_label: str


class IdentifiedHazardService:
    def __init__(self):
        self.repository = IdentifiedHazardRepository()

    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[IdentifiedHazardRow]:
        hazards = self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=include_inactive,
        )
        rows = [self._to_row(hazard) for hazard in hazards]
        return self._sort_rows(rows)

    def get_by_id(self, hazard_id: int | None) -> IdentifiedHazard | None:
        if not hazard_id:
            return None
        return self.repository.get_by_id(hazard_id)

    def count_active_for_inventory_item(self, inventory_item_id: int) -> int:
        return self.repository.count_active_for_inventory_item(inventory_item_id)

    def count_active_by_inventory_items(self, hazard_identification_id: int) -> dict[int, int]:
        counts: dict[int, int] = {}
        for hazard in self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        ):
            counts[hazard.inventory_item_id] = counts.get(hazard.inventory_item_id, 0) + 1
        return counts

    def get_inventory_item_candidates(self, hazard_identification_id: int) -> list:
        return hazard_inventory_item_service.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        )

    def create_hazard(
        self,
        *,
        hazard_identification_id: int,
        inventory_item_id: int,
        name: str,
        description: str = "",
        note: str = "",
        source_type: str = DEFAULT_IDENTIFIED_HAZARD_SOURCE,
        active: bool = True,
    ) -> IdentifiedHazard:
        normalized_name = name.strip()
        if not normalized_name:
            raise IdentifiedHazardError("Název nebezpečí je povinný.")

        self._validate_source_type(source_type)
        self._validate_inventory_item(
            hazard_identification_id,
            inventory_item_id,
        )
        self._validate_unique_active_name(
            hazard_identification_id,
            inventory_item_id=inventory_item_id,
            name=normalized_name,
            exclude_hazard_id=None,
            active=active,
        )

        hazard = IdentifiedHazard(
            hazard_identification_id=hazard_identification_id,
            inventory_item_id=inventory_item_id,
            name=normalized_name,
            description=description.strip(),
            note=note.strip(),
            source_type=source_type,
            active=active,
        )
        return self.repository.add(hazard)

    def update_hazard(
        self,
        hazard_id: int,
        *,
        inventory_item_id: int,
        name: str,
        description: str = "",
        note: str = "",
        source_type: str = DEFAULT_IDENTIFIED_HAZARD_SOURCE,
        active: bool = True,
    ) -> IdentifiedHazard | None:
        hazard = self.repository.get_by_id(hazard_id)
        if hazard is None:
            return None

        normalized_name = name.strip()
        if not normalized_name:
            raise IdentifiedHazardError("Název nebezpečí je povinný.")

        self._validate_source_type(source_type)
        self._validate_inventory_item(
            hazard.hazard_identification_id,
            inventory_item_id,
        )
        self._validate_unique_active_name(
            hazard.hazard_identification_id,
            inventory_item_id=inventory_item_id,
            name=normalized_name,
            exclude_hazard_id=hazard_id,
            active=active,
        )

        hazard.inventory_item_id = inventory_item_id
        hazard.name = normalized_name
        hazard.description = description.strip()
        hazard.note = note.strip()
        hazard.source_type = source_type
        hazard.active = active
        hazard.updated_at = datetime.now()
        return self.repository.update(hazard)

    def activate_hazard(self, hazard_id: int) -> bool:
        hazard = self.repository.get_by_id(hazard_id)
        if hazard is None:
            return False

        self._validate_unique_active_name(
            hazard.hazard_identification_id,
            inventory_item_id=hazard.inventory_item_id,
            name=hazard.name,
            exclude_hazard_id=hazard_id,
            active=True,
        )
        hazard.active = True
        hazard.updated_at = datetime.now()
        self.repository.update(hazard)
        return True

    def deactivate_hazard(self, hazard_id: int) -> bool:
        hazard = self.repository.get_by_id(hazard_id)
        if hazard is None:
            return False
        hazard.active = False
        hazard.updated_at = datetime.now()
        self.repository.update(hazard)
        return True

    def _to_row(self, hazard: IdentifiedHazard) -> IdentifiedHazardRow:
        item = hazard_inventory_item_service.get_by_id(hazard.inventory_item_id)
        if item is None:
            inventory_item_name = "—"
            inventory_item_category = ""
            inventory_item_category_label = "—"
        else:
            inventory_item_name = item.name
            inventory_item_category = item.category
            inventory_item_category_label = HAZARD_INVENTORY_CATEGORY_LABELS.get(
                item.category,
                item.category,
            )

        return IdentifiedHazardRow(
            hazard=hazard,
            inventory_item_name=inventory_item_name,
            inventory_item_category=inventory_item_category,
            inventory_item_category_label=inventory_item_category_label,
            source_type_label=IDENTIFIED_HAZARD_SOURCE_LABELS.get(
                hazard.source_type,
                hazard.source_type,
            ),
        )

    def _sort_rows(self, rows: list[IdentifiedHazardRow]) -> list[IdentifiedHazardRow]:
        category_order = {category: index for index, category in enumerate(HAZARD_INVENTORY_CATEGORIES)}

        def sort_key(row: IdentifiedHazardRow) -> tuple:
            category_index = category_order.get(row.inventory_item_category, len(HAZARD_INVENTORY_CATEGORIES))
            return (category_index, row.inventory_item_name.casefold(), row.hazard.name.casefold())

        return czech_sorted(rows, key=sort_key)

    def _validate_source_type(self, source_type: str) -> None:
        if source_type not in IDENTIFIED_HAZARD_SOURCE_TYPES:
            raise IdentifiedHazardError("Neplatný původ nebezpečí.")

    def _validate_inventory_item(
        self,
        hazard_identification_id: int,
        inventory_item_id: int,
    ) -> None:
        item = hazard_inventory_item_service.get_by_id(inventory_item_id)
        if item is None:
            raise IdentifiedHazardError("Položka analýzy pracoviště neexistuje.")
        if item.hazard_identification_id != hazard_identification_id:
            raise IdentifiedHazardError(
                "Položka analýzy pracoviště musí patřit ke stejné identifikaci."
            )
        if not item.active:
            raise IdentifiedHazardError("Lze vybrat pouze aktivní položku analýzy pracoviště.")

    def _validate_unique_active_name(
        self,
        hazard_identification_id: int,
        *,
        inventory_item_id: int,
        name: str,
        exclude_hazard_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        normalized = normalize_hazard_name(name)
        for hazard in self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=True,
        ):
            if hazard.id == exclude_hazard_id:
                continue
            if not hazard.active:
                continue
            if hazard.inventory_item_id != inventory_item_id:
                continue
            if normalize_hazard_name(hazard.name) == normalized:
                raise IdentifiedHazardError(
                    f"U vybrané položky analýzy pracoviště již existuje aktivní nebezpečí "
                    f"s názvem „{name.strip()}“."
                )


identified_hazard_service = IdentifiedHazardService()
