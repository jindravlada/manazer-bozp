from datetime import datetime

from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
from moduly.rizeni_rizik.repository.hazard_inventory_item_repository import (
    HazardInventoryItemRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
    HazardSourceCategoryError,
    hazard_source_category_service,
)


class HazardInventoryItemError(ValueError):
    pass


def normalize_inventory_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


class HazardInventoryItemService:
    def __init__(self):
        self.repository = HazardInventoryItemRepository()

    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardInventoryItem]:
        return self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=include_inactive,
        )

    def get_by_category(
        self,
        hazard_identification_id: int,
        category: str,
        *,
        include_inactive: bool = True,
    ) -> list[HazardInventoryItem]:
        items = self.get_for_identification(
            hazard_identification_id,
            include_inactive=include_inactive,
        )
        return [item for item in items if item.category == category]

    def get_by_id(self, item_id: int | None) -> HazardInventoryItem | None:
        if not item_id:
            return None
        return self.repository.get_by_id(item_id)

    def count_active_by_category(self, hazard_identification_id: int) -> dict[str, int]:
        codes = hazard_source_category_service.ordered_codes(include_inactive=True)
        counts = {category: 0 for category in codes}
        for item in self.get_for_identification(
            hazard_identification_id,
            include_inactive=False,
        ):
            counts[item.category] = counts.get(item.category, 0) + 1
        return counts

    def create_item(
        self,
        *,
        hazard_identification_id: int,
        category: str,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> HazardInventoryItem:
        normalized_name = name.strip()
        if not normalized_name:
            raise HazardInventoryItemError("Název je povinný.")
        try:
            validated_category = hazard_source_category_service.validate_for_new(category)
        except HazardSourceCategoryError as error:
            raise HazardInventoryItemError(str(error)) from error
        self._validate_unique_active_name(
            hazard_identification_id,
            category=validated_category,
            name=normalized_name,
            exclude_item_id=None,
            active=active,
        )

        item = HazardInventoryItem(
            hazard_identification_id=hazard_identification_id,
            category=validated_category,
            name=normalized_name,
            description=description.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(
                hazard_identification_id,
                validated_category,
            ),
        )
        return self.repository.add(item)

    def update_item(
        self,
        item_id: int,
        *,
        category: str,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> HazardInventoryItem | None:
        item = self.repository.get_by_id(item_id)
        if item is None:
            return None

        normalized_name = name.strip()
        if not normalized_name:
            raise HazardInventoryItemError("Název je povinný.")
        try:
            validated_category = hazard_source_category_service.validate_existing(
                category,
                previous_code=item.category,
            )
        except HazardSourceCategoryError as error:
            raise HazardInventoryItemError(str(error)) from error
        self._validate_unique_active_name(
            item.hazard_identification_id,
            category=validated_category,
            name=normalized_name,
            exclude_item_id=item_id,
            active=active,
        )

        item.category = validated_category
        item.name = normalized_name
        item.description = description.strip()
        item.active = active
        item.updated_at = datetime.now()
        return self.repository.update(item)

    def activate_item(self, item_id: int) -> bool:
        item = self.repository.get_by_id(item_id)
        if item is None:
            return False
        self._validate_unique_active_name(
            item.hazard_identification_id,
            category=item.category,
            name=item.name,
            exclude_item_id=item_id,
            active=True,
        )
        item.active = True
        item.updated_at = datetime.now()
        self.repository.update(item)
        return True

    def deactivate_item(self, item_id: int) -> bool:
        item = self.repository.get_by_id(item_id)
        if item is None:
            return False
        item.active = False
        item.updated_at = datetime.now()
        self.repository.update(item)
        return True

    def _validate_category(self, category: str, *, previous_code: str | None = None) -> str:
        try:
            if previous_code is None:
                return hazard_source_category_service.validate_known(category)
            return hazard_source_category_service.validate_existing(
                category,
                previous_code=previous_code,
            )
        except HazardSourceCategoryError as error:
            raise HazardInventoryItemError(str(error)) from error

    def _validate_unique_active_name(
        self,
        hazard_identification_id: int,
        *,
        category: str,
        name: str,
        exclude_item_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        normalized = normalize_inventory_name(name)
        for item in self.get_for_identification(hazard_identification_id, include_inactive=True):
            if item.id == exclude_item_id:
                continue
            if not item.active:
                continue
            if item.category != category:
                continue
            if normalize_inventory_name(item.name) == normalized:
                label = hazard_source_category_service.label_for(category)
                raise HazardInventoryItemError(
                    f"V kategorii {label} již existuje aktivní položka "
                    f"s názvem „{name.strip()}“."
                )


hazard_inventory_item_service = HazardInventoryItemService()
