from dataclasses import dataclass
from datetime import datetime

from core.utils.czech_sort import czech_sorted
from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORIES
from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
from moduly.rizeni_rizik.repository.hazard_event_repository import HazardEventRepository
from moduly.rizeni_rizik.sluzby.identified_hazard_service import (
    IdentifiedHazardRow,
    identified_hazard_service,
)


class HazardEventError(ValueError):
    pass


def normalize_event_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


@dataclass
class HazardEventRow:
    event: HazardEvent
    hazard_name: str
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
        hazard_rows = {
            row.hazard.id: row
            for row in identified_hazard_service.get_for_identification(
                hazard_identification_id,
                include_inactive=True,
            )
        }
        rows = [self._to_row(event, hazard_rows) for event in events]
        return self._sort_rows(rows)

    def get_by_id(self, event_id: int | None) -> HazardEvent | None:
        if not event_id:
            return None
        return self.repository.get_by_id(event_id)

    def count_active_for_hazard(self, identified_hazard_id: int) -> int:
        return self.repository.count_active_for_hazard(identified_hazard_id)

    def count_active_by_hazards(self, hazard_identification_id: int) -> dict[int, int]:
        counts: dict[int, int] = {}
        for event in self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        ):
            counts[event.identified_hazard_id] = counts.get(event.identified_hazard_id, 0) + 1
        return counts

    def get_hazard_candidates(self, hazard_identification_id: int) -> list[IdentifiedHazardRow]:
        return identified_hazard_service.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        )

    def create_event(
        self,
        *,
        hazard_identification_id: int,
        identified_hazard_id: int,
        name: str,
        description: str = "",
        note: str = "",
        active: bool = True,
    ) -> HazardEvent:
        normalized_name = name.strip()
        if not normalized_name:
            raise HazardEventError("Název události je povinný.")

        self._validate_hazard(hazard_identification_id, identified_hazard_id)
        self._validate_unique_active_name(
            identified_hazard_id,
            name=normalized_name,
            exclude_event_id=None,
            active=active,
        )

        event = HazardEvent(
            identified_hazard_id=identified_hazard_id,
            name=normalized_name,
            description=description.strip(),
            note=note.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(identified_hazard_id),
        )
        return self.repository.add(event)

    def update_event(
        self,
        event_id: int,
        *,
        hazard_identification_id: int,
        identified_hazard_id: int,
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

        self._validate_hazard(hazard_identification_id, identified_hazard_id)
        self._validate_unique_active_name(
            identified_hazard_id,
            name=normalized_name,
            exclude_event_id=event_id,
            active=active,
        )

        event.identified_hazard_id = identified_hazard_id
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
            event.identified_hazard_id,
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
        hazard_rows: dict[int, IdentifiedHazardRow],
    ) -> HazardEventRow:
        hazard_row = hazard_rows.get(event.identified_hazard_id)
        if hazard_row is None:
            return HazardEventRow(
                event=event,
                hazard_name="—",
                inventory_item_name="—",
                inventory_item_category="",
                inventory_item_category_label="—",
            )

        return HazardEventRow(
            event=event,
            hazard_name=hazard_row.hazard.name,
            inventory_item_name=hazard_row.inventory_item_name,
            inventory_item_category=hazard_row.inventory_item_category,
            inventory_item_category_label=hazard_row.inventory_item_category_label,
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
                row.hazard_name.casefold(),
                row.event.name.casefold(),
            )

        return czech_sorted(rows, key=sort_key)

    def _validate_hazard(
        self,
        hazard_identification_id: int,
        identified_hazard_id: int,
    ) -> None:
        hazard = identified_hazard_service.get_by_id(identified_hazard_id)
        if hazard is None:
            raise HazardEventError("Nebezpečí neexistuje.")
        if hazard.hazard_identification_id != hazard_identification_id:
            raise HazardEventError("Nebezpečí musí patřit ke stejné identifikaci.")
        if not hazard.active:
            raise HazardEventError("Lze vybrat pouze aktivní nebezpečí.")

    def _validate_unique_active_name(
        self,
        identified_hazard_id: int,
        *,
        name: str,
        exclude_event_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        normalized = normalize_event_name(name)
        for event in self.repository.get_for_identified_hazard(
            identified_hazard_id,
            include_inactive=True,
        ):
            if event.id == exclude_event_id:
                continue
            if not event.active:
                continue
            if normalize_event_name(event.name) == normalized:
                raise HazardEventError(
                    f"U vybraného nebezpečí již existuje aktivní nežádoucí událost "
                    f"s názvem „{name.strip()}“."
                )


hazard_event_service = HazardEventService()
