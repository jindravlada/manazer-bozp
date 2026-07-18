"""Služba číselníku kategorií zdrojů rizik."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.constants import (
    DEFAULT_HAZARD_SOURCE_CATEGORIES,
    HAZARD_INVENTORY_CATEGORIES,
)
from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.modely.hazard_source_category import HazardSourceCategory
from moduly.rizeni_rizik.repository.hazard_source_category_repository import (
    HazardSourceCategoryRepository,
)


class HazardSourceCategoryError(ValueError):
    pass


def normalize_category_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


class HazardSourceCategoryService:
    def __init__(self) -> None:
        self.repository = HazardSourceCategoryRepository()

    def get_all(self, *, include_inactive: bool = False) -> list[HazardSourceCategory]:
        return self.repository.get_all(include_inactive=include_inactive)

    def get_active_all(self) -> list[HazardSourceCategory]:
        return self.repository.get_all(include_inactive=False)

    def get_by_id(self, category_id: int | None) -> HazardSourceCategory | None:
        if not category_id:
            return None
        return self.repository.get_by_id(category_id)

    def get_by_code(self, code: str | None) -> HazardSourceCategory | None:
        if not code:
            return None
        return self.repository.get_by_code(code)

    def label_for(self, code: str | None) -> str:
        if not code:
            return ""
        category = self.get_by_code(code)
        if category is not None:
            return category.name
        # Fallback pro legacy kódy před migrací / chybějící řádek.
        for default_code, name, _description, _order in DEFAULT_HAZARD_SOURCE_CATEGORIES:
            if default_code == code:
                return name
        return code

    def ordered_codes(self, *, include_inactive: bool = True) -> list[str]:
        return [item.code for item in self.get_all(include_inactive=include_inactive)]

    def active_codes(self) -> list[str]:
        return [item.code for item in self.get_active_all()]

    def create_category(
        self,
        *,
        name: str,
        description: str = "",
        active: bool = True,
        sort_order: int | None = None,
        code: str | None = None,
    ) -> HazardSourceCategory:
        normalized_name = self._validate_name(name)
        self._ensure_unique_name(normalized_name)
        resolved_code = (code or "").strip() or self._generate_code(normalized_name)
        if self.repository.get_by_code(resolved_code) is not None:
            raise HazardSourceCategoryError(
                f"Kategorie s kódem „{resolved_code}“ již existuje.",
            )
        category = HazardSourceCategory(
            code=resolved_code,
            name=normalized_name,
            description=(description or "").strip(),
            active=active,
            sort_order=(
                sort_order if sort_order is not None else self.repository.next_sort_order()
            ),
        )
        return self.repository.add(category)

    def update_category(
        self,
        category_id: int,
        *,
        name: str,
        description: str = "",
        active: bool = True,
        sort_order: int | None = None,
    ) -> HazardSourceCategory | None:
        category = self.repository.get_by_id(category_id)
        if category is None:
            return None

        normalized_name = self._validate_name(name)
        self._ensure_unique_name(normalized_name, exclude_category_id=category_id)

        was_active = bool(category.active)
        if was_active and not active:
            self._ensure_can_deactivate(category.code)

        category.name = normalized_name
        category.description = (description or "").strip()
        category.active = active
        if sort_order is not None:
            category.sort_order = sort_order
        category.updated_at = datetime.now()
        return self.repository.update(category)

    def activate(self, category_id: int) -> bool:
        category = self.repository.get_by_id(category_id)
        if category is None:
            return False
        self._ensure_unique_name(category.name, exclude_category_id=category_id)
        return self.repository.activate(category_id)

    def deactivate(self, category_id: int) -> bool:
        category = self.repository.get_by_id(category_id)
        if category is None:
            return False
        self._ensure_can_deactivate(category.code)
        return self.repository.deactivate(category_id)

    def count_active_sources(self, code: str) -> int:
        """Počet aktivních katalogových zdrojů + aktivních položek identifikace."""
        with get_session() as session:
            templates = int(
                session.scalar(
                    select(func.count())
                    .select_from(HazardLibraryTemplate)
                    .where(
                        HazardLibraryTemplate.category == code,
                        HazardLibraryTemplate.active.is_(True),
                    )
                )
                or 0
            )
            items = int(
                session.scalar(
                    select(func.count())
                    .select_from(HazardInventoryItem)
                    .where(
                        HazardInventoryItem.category == code,
                        HazardInventoryItem.active.is_(True),
                    )
                )
                or 0
            )
        return templates + items

    def validate_for_new(self, code: str) -> str:
        category = self.get_by_code(code)
        if category is None or not category.active:
            raise HazardSourceCategoryError("Vyberte aktivní kategorii zdroje rizika.")
        return category.code

    def validate_known(self, code: str) -> str:
        """Povolí existující kód i u neaktivní kategorie (převzetí / sync z katalogu)."""
        category = self.get_by_code(code)
        if category is not None:
            return category.code
        if code in HAZARD_INVENTORY_CATEGORIES:
            return code
        raise HazardSourceCategoryError("Neplatná kategorie zdroje rizika.")

    def validate_existing(self, code: str, *, previous_code: str | None = None) -> str:
        """Validace při editaci – aktuální (i neaktivní) kategorie je povolena."""
        category = self.get_by_code(code)
        if category is None:
            # Legacy kód ze starší DB bez řádku číselníku.
            if code in HAZARD_INVENTORY_CATEGORIES:
                return code
            raise HazardSourceCategoryError("Neplatná kategorie zdroje rizika.")
        if category.active:
            return category.code
        if previous_code == code:
            return category.code
        raise HazardSourceCategoryError(
            "Neaktivní kategorii nelze nově přiřadit. Vyberte aktivní kategorii.",
        )

    def _ensure_can_deactivate(self, code: str) -> None:
        count = self.count_active_sources(code)
        if count:
            noun = "aktivní zdroj" if count == 1 else "aktivních zdrojů"
            raise HazardSourceCategoryError(
                f"Kategorie obsahuje {count} {noun}. "
                "Před deaktivací přesuňte zdroje do jiné aktivní kategorie."
            )

    def _validate_name(self, name: str) -> str:
        normalized = " ".join(name.strip().split())
        if not normalized:
            raise HazardSourceCategoryError("Název kategorie je povinný.")
        return normalized

    def _ensure_unique_name(
        self,
        name: str,
        *,
        exclude_category_id: int | None = None,
    ) -> None:
        normalized = normalize_category_name(name)
        for category in self.repository.get_all(include_inactive=True):
            if category.id == exclude_category_id:
                continue
            if normalize_category_name(category.name) == normalized:
                raise HazardSourceCategoryError(
                    f"Kategorie „{category.name}“ již existuje.",
                )

    def _generate_code(self, name: str) -> str:
        base = "".join(ch if ch.isalnum() else "_" for ch in name.casefold())
        base = "_".join(part for part in base.split("_") if part)[:28] or "category"
        candidate = base
        suffix = 2
        while self.repository.get_by_code(candidate) is not None:
            candidate = f"{base[:26]}_{suffix}"
            suffix += 1
        return candidate


hazard_source_category_service = HazardSourceCategoryService()
