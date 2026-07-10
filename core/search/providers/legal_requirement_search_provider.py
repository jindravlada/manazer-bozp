"""Poskytovatel globálního vyhledávání pro řídicí procesy."""

from moduly.pravni_pozadavky.constants import (
    legal_requirement_merged_target_label,
    legal_requirement_process_label,
    legal_requirement_responsible_label,
    process_code_sort_key,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service

from core.search.constants import (
    ENTITY_TYPE_LEGAL_REQUIREMENT,
    GROUP_LEGAL_REQUIREMENTS,
    RESULT_TYPE_LEGAL_REQUIREMENT,
)
from core.search.global_search_result import GlobalSearchResult
from core.search.search_provider import SearchProvider
from core.search.search_utils import contains_query


class LegalRequirementSearchProvider(SearchProvider):
    provider_key = "legal_requirements"
    module_key = "pravni_pozadavky"
    module_label = GROUP_LEGAL_REQUIREMENTS

    def search(self, query: str, *, limit: int) -> list[GlobalSearchResult]:
        results: list[GlobalSearchResult] = []

        for requirement in legal_requirement_service.get_all():
            searchable_values = (
                requirement.process_code,
                legal_requirement_process_label(requirement),
                requirement.requirement_summary,
                requirement.organization_impact,
                requirement.process_inputs,
                requirement.process_outputs,
                legal_requirement_responsible_label(requirement),
                requirement.responsible_role_name,
                requirement.responsible_person_name,
            )
            if not contains_query(query, *searchable_values):
                continue

            search_text = " ".join(str(value) for value in searchable_values if value)
            results.append(
                GlobalSearchResult(
                    entity_type=ENTITY_TYPE_LEGAL_REQUIREMENT,
                    entity_id=requirement.id,
                    title=legal_requirement_merged_target_label(requirement),
                    subtitle=RESULT_TYPE_LEGAL_REQUIREMENT,
                    search_text=search_text,
                    sort_key=process_code_sort_key(requirement),
                    module_key=self.module_key,
                    group_label=GROUP_LEGAL_REQUIREMENTS,
                )
            )

        results.sort(key=lambda item: item.sort_key)
        return results[:limit]
