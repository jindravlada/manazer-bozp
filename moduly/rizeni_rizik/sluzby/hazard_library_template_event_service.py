from datetime import datetime

from moduly.rizeni_rizik.modely.hazard_library_template_event import HazardLibraryTemplateEvent
from moduly.rizeni_rizik.repository.hazard_library_template_event_repository import (
    HazardLibraryTemplateEventRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_item_service import (
    hazard_library_template_item_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_version import (
    bump_template_content_version,
)


class HazardLibraryTemplateEventError(ValueError):
    pass


def normalize_template_event_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


class HazardLibraryTemplateEventService:
    def __init__(self):
        self.repository = HazardLibraryTemplateEventRepository()

    def get_for_template_item(
        self,
        template_item_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateEvent]:
        return self.repository.get_for_template_item(
            template_item_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, event_id: int | None) -> HazardLibraryTemplateEvent | None:
        if not event_id:
            return None
        return self.repository.get_by_id(event_id)

    def count_active_for_template_item(self, template_item_id: int) -> int:
        return self.repository.count_active_for_template_item(template_item_id)

    def count_active_by_template_items(self, template_id: int) -> dict[int, int]:
        counts: dict[int, int] = {}
        for item in hazard_library_template_item_service.get_for_template(
            template_id,
            include_inactive=True,
        ):
            counts[item.id] = self.repository.count_active_for_template_item(item.id)
        return counts

    def create_event(
        self,
        *,
        template_id: int,
        template_item_id: int,
        name: str,
        description: str = "",
        note: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateEvent:
        normalized_name = name.strip()
        if not normalized_name:
            raise HazardLibraryTemplateEventError("Název události je povinný.")

        self._validate_template_item(template_id, template_item_id)
        self._validate_unique_active_name(
            template_item_id,
            name=normalized_name,
            exclude_event_id=None,
            active=active,
        )

        event = HazardLibraryTemplateEvent(
            template_item_id=template_item_id,
            name=normalized_name,
            description=description.strip(),
            note=note.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(template_item_id),
        )
        saved = self.repository.add(event)
        bump_template_content_version(template_id)
        return saved

    def update_event(
        self,
        event_id: int,
        *,
        template_id: int,
        template_item_id: int,
        name: str,
        description: str = "",
        note: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateEvent | None:
        event = self.repository.get_by_id(event_id)
        if event is None:
            return None

        normalized_name = name.strip()
        if not normalized_name:
            raise HazardLibraryTemplateEventError("Název události je povinný.")

        self._validate_template_item(template_id, template_item_id)
        self._validate_unique_active_name(
            template_item_id,
            name=normalized_name,
            exclude_event_id=event_id,
            active=active,
        )

        event.template_item_id = template_item_id
        event.name = normalized_name
        event.description = description.strip()
        event.note = note.strip()
        event.active = active
        event.updated_at = datetime.now()
        saved = self.repository.update(event)
        bump_template_content_version(template_id)
        return saved

    def activate_event(self, event_id: int) -> bool:
        event = self.repository.get_by_id(event_id)
        if event is None:
            return False
        template_id = self._template_id_for_event(event)
        self._validate_unique_active_name(
            event.template_item_id,
            name=event.name,
            exclude_event_id=event_id,
            active=True,
        )
        event.active = True
        event.updated_at = datetime.now()
        self.repository.update(event)
        bump_template_content_version(template_id)
        return True

    def deactivate_event(self, event_id: int) -> bool:
        event = self.repository.get_by_id(event_id)
        if event is None:
            return False
        template_id = self._template_id_for_event(event)
        event.active = False
        event.updated_at = datetime.now()
        self.repository.update(event)
        bump_template_content_version(template_id)
        return True

    def get_template_id_for_event(self, event_id: int) -> int | None:
        event = self.repository.get_by_id(event_id)
        if event is None:
            return None
        return self._template_id_for_event(event)

    def _template_id_for_event(self, event: HazardLibraryTemplateEvent) -> int:
        item = hazard_library_template_item_service.get_by_id(event.template_item_id)
        if item is None:
            raise HazardLibraryTemplateEventError("Položka vzoru neexistuje.")
        return item.template_id

    def _validate_template_item(self, template_id: int, template_item_id: int) -> None:
        item = hazard_library_template_item_service.get_by_id(template_item_id)
        if item is None or item.template_id != template_id:
            raise HazardLibraryTemplateEventError("Položka vzoru nepatří do zvoleného vzoru.")

    def _validate_unique_active_name(
        self,
        template_item_id: int,
        *,
        name: str,
        exclude_event_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        normalized = normalize_template_event_name(name)
        for event in self.get_for_template_item(template_item_id, include_inactive=True):
            if event.id == exclude_event_id:
                continue
            if not event.active:
                continue
            if normalize_template_event_name(event.name) == normalized:
                raise HazardLibraryTemplateEventError(
                    f"U položky vzoru již existuje aktivní událost s názvem „{name.strip()}“."
                )


hazard_library_template_event_service = HazardLibraryTemplateEventService()
