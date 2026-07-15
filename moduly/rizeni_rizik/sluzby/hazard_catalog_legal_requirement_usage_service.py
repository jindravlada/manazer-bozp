"""Odchozí použití katalogových zdrojů rizik z právních požadavků (R19a)."""

from __future__ import annotations

from dataclasses import dataclass

from core.utils.czech_sort import czech_sorted
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_LABELS
from moduly.rizeni_rizik.repository.hazard_library_template_legal_link_repository import (
    HazardLibraryTemplateLegalLinkRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
)


@dataclass(frozen=True)
class HazardCatalogSourceUsage:
    template_id: int
    name: str
    category_label: str
    version_number: int
    active: bool


class HazardCatalogLegalRequirementUsageService:
    def __init__(self):
        self.legal_link_repository = HazardLibraryTemplateLegalLinkRepository()

    def list_sources_for_requirement(
        self,
        requirement_id: int,
    ) -> tuple[HazardCatalogSourceUsage, ...]:
        return self._list_sources_for_requirement_ids([requirement_id])

    def list_sources_for_process(
        self,
        process_id: int,
    ) -> tuple[HazardCatalogSourceUsage, ...]:
        child_ids = [
            child.id
            for child in legal_requirement_service.list_children(process_id)
            if child.active
        ]
        return self._list_sources_for_requirement_ids(child_ids)

    def _list_sources_for_requirement_ids(
        self,
        requirement_ids: list[int],
    ) -> tuple[HazardCatalogSourceUsage, ...]:
        template_ids = self.legal_link_repository.list_active_template_ids_for_requirements(
            requirement_ids,
        )
        usages: list[HazardCatalogSourceUsage] = []
        for template_id in template_ids:
            template = hazard_library_template_service.get_by_id(template_id)
            if template is None or not template.active:
                continue
            usages.append(
                HazardCatalogSourceUsage(
                    template_id=template.id,
                    name=template.name,
                    category_label=HAZARD_INVENTORY_CATEGORY_LABELS.get(
                        template.category,
                        template.category,
                    ),
                    version_number=template.version_number,
                    active=template.active,
                ),
            )
        return tuple(
            czech_sorted(usages, key=lambda item: item.name.casefold()),
        )


hazard_catalog_legal_requirement_usage_service = HazardCatalogLegalRequirementUsageService()
