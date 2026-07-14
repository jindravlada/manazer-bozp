from dataclasses import dataclass
from datetime import datetime

from core.utils.czech_sort import czech_sorted
from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
)
from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
from moduly.rizeni_rizik.repository.hazard_event_repository import HazardEventRepository
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    hazard_inventory_item_service,
)


class HazardEventError(ValueError):
    pass


def normalize_event_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


@dataclass
class HazardEventRow:
    event: HazardEvent
    inventory_item_name: str
    inventory_item_category: str
    inventory_item_category_label: str


class HazardEventService:
    def __init__(self):
        self.repository = HazardEventRepository()

    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardEventRow]:
        events = self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=include_inactive,
        )
        items = {
            item.id: item
            for item in hazard_inventory_item_service.get_for_identification(
                hazard_identification_id,
                include_inactive=True,
            )
        }
        rows = [self._to_row(event, items) for event in events]
        return self._sort_rows(rows)

    def get_for_inventory_item(
        self,
        inventory_item_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardEvent]:
        return self.repository.get_for_inventory_item(
            inventory_item_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, event_id: int | None) -> HazardEvent | None:
        if not event_id:
            return None
        return self.repository.get_by_id(event_id)

    def count_active_for_inventory_item(self, inventory_item_id: int) -> int:
        return self.repository.count_active_for_inventory_item(inventory_item_id)

    def count_active_by_inventory_items(self, hazard_identification_id: int) -> dict[int, int]:
        counts: dict[int, int] = {}
        for event in self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        ):
            counts[event.inventory_item_id] = counts.get(event.inventory_item_id, 0) + 1
        return counts

    def get_inventory_item_candidates(
        self,
        hazard_identification_id: int,
    ) -> list[HazardInventoryItem]:
        return hazard_inventory_item_service.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        )

    def create_event(
        self,
        *,
        hazard_identification_id: int,
        inventory_item_id: int,
        name: str,
        description: str = "",
        note: str = "",
        active: bool = True,
    ) -> HazardEvent:
        normalized_name = name.strip()
        if not normalized_name:
            raise HazardEventError("Název události je povinný.")

        self._validate_inventory_item(hazard_identification_id, inventory_item_id)
        self._validate_unique_active_name(
            inventory_item_id,
            name=normalized_name,
            exclude_event_id=None,
            active=active,
        )

        event = HazardEvent(
            inventory_item_id=inventory_item_id,
            name=normalized_name,
            description=description.strip(),
            note=note.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(inventory_item_id),
        )
        return self.repository.add(event)

    def update_event(
        self,
        event_id: int,
        *,
        hazard_identification_id: int,
        inventory_item_id: int,
        name: str,
        description: str = "",
        note: str = "",
        active: bool = True,
    ) -> HazardEvent | None:
        event = self.repository.get_by_id(event_id)
        if event is None:
            return None

        normalized_name = name.strip()
        if not normalized_name:
            raise HazardEventError("Název události je povinný.")

        self._validate_inventory_item(hazard_identification_id, inventory_item_id)
        self._validate_unique_active_name(
            inventory_item_id,
            name=normalized_name,
            exclude_event_id=event_id,
            active=active,
        )

        event.inventory_item_id = inventory_item_id
        event.name = normalized_name
        event.description = description.strip()
        event.note = note.strip()
        event.active = active
        event.updated_at = datetime.now()
        return self.repository.update(event)

    def activate_event(self, event_id: int) -> bool:
        event = self.repository.get_by_id(event_id)
        if event is None:
            return False

        self._validate_unique_active_name(
            event.inventory_item_id,
            name=event.name,
            exclude_event_id=event_id,
            active=True,
        )
        event.active = True
        event.updated_at = datetime.now()
        self.repository.update(event)
        return True

    def deactivate_event(self, event_id: int) -> bool:
        event = self.repository.get_by_id(event_id)
        if event is None:
            return False
        event.active = False
        event.updated_at = datetime.now()
        self.repository.update(event)
        return True

    def _to_row(
        self,
        event: HazardEvent,
        items: dict[int, HazardInventoryItem],
    ) -> HazardEventRow:
        item = items.get(event.inventory_item_id)
        if item is None:
            return HazardEventRow(
                event=event,
                inventory_item_name="—",
                inventory_item_category="",
                inventory_item_category_label="—",
            )

        return HazardEventRow(
            event=event,
            inventory_item_name=item.name,
            inventory_item_category=item.category,
            inventory_item_category_label=HAZARD_INVENTORY_CATEGORY_LABELS.get(
                item.category,
                item.category,
            ),
        )

    def _sort_rows(self, rows: list[HazardEventRow]) -> list[HazardEventRow]:
        category_order = {
            category: index for index, category in enumerate(HAZARD_INVENTORY_CATEGORIES)
        }

        def sort_key(row: HazardEventRow) -> tuple:
            category_index = category_order.get(
                row.inventory_item_category,
                len(HAZARD_INVENTORY_CATEGORIES),
            )
            return (
                category_index,
                row.inventory_item_name.casefold(),
                row.event.name.casefold(),
            )

        return czech_sorted(rows, key=sort_key)

    def _validate_inventory_item(
        self,
        hazard_identification_id: int,
        inventory_item_id: int,
    ) -> None:
        item = hazard_inventory_item_service.get_by_id(inventory_item_id)
        if item is None:
            raise HazardEventError("Zdroj analýzy neexistuje.")
        if item.hazard_identification_id != hazard_identification_id:
            raise HazardEventError("Zdroj analýzy musí patřit ke stejné identifikaci.")
        if not item.active:
            raise HazardEventError("Lze vybrat pouze aktivní zdroj analýzy.")

    def _validate_unique_active_name(
        self,
        inventory_item_id: int,
        *,
        name: str,
        exclude_event_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        normalized = normalize_event_name(name)
        for event in self.repository.get_for_inventory_item(
            inventory_item_id,
            include_inactive=True,
        ):
            if event.id == exclude_event_id:
                continue
            if not event.active:
                continue
            if normalize_event_name(event.name) == normalized:
                raise HazardEventError(
                    f"U vybraného zdroje analýzy již existuje aktivní nežádoucí událost "
                    f"s názvem „{name.strip()}“."
                )


hazard_event_service = HazardEventService()
