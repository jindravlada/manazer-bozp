from datetime import datetime

from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
)
from moduly.rizeni_rizik.modely.hazard_library_template_item import HazardLibraryTemplateItem
from moduly.rizeni_rizik.repository.hazard_library_template_item_repository import (
    HazardLibraryTemplateItemRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_version import (
    bump_template_content_version,
)


class HazardLibraryTemplateItemError(ValueError):
    pass


def normalize_template_item_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


class HazardLibraryTemplateItemService:
    def __init__(self):
        self.repository = HazardLibraryTemplateItemRepository()

    def get_for_template(
        self,
        template_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateItem]:
        return self.repository.get_for_template(
            template_id,
            include_inactive=include_inactive,
        )

    def get_by_category(
        self,
        template_id: int,
        category: str,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateItem]:
        return [
            item
            for item in self.get_for_template(template_id, include_inactive=include_inactive)
            if item.category == category
        ]

    def get_by_id(self, item_id: int | None) -> HazardLibraryTemplateItem | None:
        if not item_id:
            return None
        return self.repository.get_by_id(item_id)

    def count_active_by_category(self, template_id: int) -> dict[str, int]:
        counts = {category: 0 for category in HAZARD_INVENTORY_CATEGORIES}
        for item in self.get_for_template(template_id, include_inactive=False):
            if item.category in counts:
                counts[item.category] += 1
        return counts

    def create_item(
        self,
        *,
        template_id: int,
        category: str,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateItem:
        normalized_name = name.strip()
        if not normalized_name:
            raise HazardLibraryTemplateItemError("Název položky vzoru je povinný.")
        self._validate_category(category)
        self._validate_unique_active_name(
            template_id,
            category=category,
            name=normalized_name,
            exclude_item_id=None,
            active=active,
        )

        item = HazardLibraryTemplateItem(
            template_id=template_id,
            category=category,
            name=normalized_name,
            description=description.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(template_id, category),
        )
        saved = self.repository.add(item)
        bump_template_content_version(template_id)
        return saved

    def update_item(
        self,
        item_id: int,
        *,
        category: str,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateItem | None:
        item = self.repository.get_by_id(item_id)
        if item is None:
            return None

        normalized_name = name.strip()
        if not normalized_name:
            raise HazardLibraryTemplateItemError("Název položky vzoru je povinný.")
        self._validate_category(category)
        self._validate_unique_active_name(
            item.template_id,
            category=category,
            name=normalized_name,
            exclude_item_id=item_id,
            active=active,
        )

        item.category = category
        item.name = normalized_name
        item.description = description.strip()
        item.active = active
        item.updated_at = datetime.now()
        saved = self.repository.update(item)
        bump_template_content_version(item.template_id)
        return saved

    def activate_item(self, item_id: int) -> bool:
        item = self.repository.get_by_id(item_id)
        if item is None:
            return False
        self._validate_unique_active_name(
            item.template_id,
            category=item.category,
            name=item.name,
            exclude_item_id=item_id,
            active=True,
        )
        item.active = True
        item.updated_at = datetime.now()
        self.repository.update(item)
        bump_template_content_version(item.template_id)
        return True

    def deactivate_item(self, item_id: int) -> bool:
        item = self.repository.get_by_id(item_id)
        if item is None:
            return False
        item.active = False
        item.updated_at = datetime.now()
        self.repository.update(item)
        bump_template_content_version(item.template_id)
        return True

    def _validate_category(self, category: str) -> None:
        if category not in HAZARD_INVENTORY_CATEGORIES:
            raise HazardLibraryTemplateItemError("Neplatná kategorie položky analýzy.")

    def _validate_unique_active_name(
        self,
        template_id: int,
        *,
        category: str,
        name: str,
        exclude_item_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return

        normalized = normalize_template_item_name(name)
        for item in self.get_for_template(template_id, include_inactive=True):
            if item.id == exclude_item_id:
                continue
            if not item.active:
                continue
            if item.category != category:
                continue
            if normalize_template_item_name(item.name) == normalized:
                label = HAZARD_INVENTORY_CATEGORY_LABELS.get(category, category)
                raise HazardLibraryTemplateItemError(
                    f"V kategorii {label} již existuje aktivní položka "
                    f"s názvem „{name.strip()}“."
                )


hazard_library_template_item_service = HazardLibraryTemplateItemService()
