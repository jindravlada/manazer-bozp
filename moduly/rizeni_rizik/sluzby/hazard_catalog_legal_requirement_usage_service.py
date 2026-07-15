"""Použití katalogových zdrojů rizik z právních předpisů a procesů (R19a, R19b)."""

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

    def list_sources_for_document(
        self,
        document_id: int,
    ) -> tuple[HazardCatalogSourceUsage, ...]:
        return self._list_sources_for_template_ids(
            self.legal_link_repository.list_active_template_ids_for_documents([document_id]),
        )

    def list_sources_for_requirement(
        self,
        requirement_id: int,
    ) -> tuple[HazardCatalogSourceUsage, ...]:
        """Zdroje u požadavku: přímá vazba na předpis požadavku + legacy vazby."""
        template_ids: list[int] = []
        requirement = legal_requirement_service.get_by_id(requirement_id)
        if requirement is not None and requirement.legal_document_id is not None:
            template_ids.extend(
                self.legal_link_repository.list_active_template_ids_for_documents(
                    [requirement.legal_document_id],
                ),
            )
        template_ids.extend(
            self.legal_link_repository.list_active_template_ids_for_requirements(
                [requirement_id],
            ),
        )
        return self._list_sources_for_template_ids(template_ids)

    def list_sources_for_process(
        self,
        process_id: int,
    ) -> tuple[HazardCatalogSourceUsage, ...]:
        """
        Processo → podřízené požadavky → jejich předpis → zdroje rizik.
        Každý zdroj jen jednou.
        """
        document_ids: list[int] = []
        for child in legal_requirement_service.list_children(process_id):
            if not child.active:
                continue
            if child.legal_document_id is not None:
                document_ids.append(int(child.legal_document_id))
        return self._list_sources_for_template_ids(
            self.legal_link_repository.list_active_template_ids_for_documents(document_ids),
        )

    def _list_sources_for_template_ids(
        self,
        template_ids: list[int],
    ) -> tuple[HazardCatalogSourceUsage, ...]:
        seen: set[int] = set()
        usages: list[HazardCatalogSourceUsage] = []
        for template_id in template_ids:
            if template_id in seen:
                continue
            seen.add(template_id)
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
