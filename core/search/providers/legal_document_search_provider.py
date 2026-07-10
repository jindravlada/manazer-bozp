"""Poskytovatel globálního vyhledávání pro právní předpisy."""

from moduly.pravni_pozadavky.constants import legal_document_regulation_number
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service

from core.search.constants import (
    ENTITY_TYPE_LEGAL_DOCUMENT,
    GROUP_LEGAL_DOCUMENTS,
    RESULT_TYPE_LEGAL_DOCUMENT,
)
from core.search.global_search_result import GlobalSearchResult
from core.search.search_provider import SearchProvider
from core.search.search_utils import contains_query


def _document_title_label(document) -> str:
    regulation_number = legal_document_regulation_number(document)
    title = (document.title or "").strip()
    if regulation_number and title:
        return f"{regulation_number} – {title}"
    if regulation_number:
        return regulation_number
    if title:
        return title
    return f"Předpis #{document.id}"


def _document_sort_key(document) -> tuple:
    number = (document.number or "").strip()
    year = document.year if document.year is not None else 0
    title = (document.title or "").strip().casefold()
    return (number, year, title)


class LegalDocumentSearchProvider(SearchProvider):
    provider_key = "legal_documents"
    module_key = "pravni_pozadavky"
    module_label = GROUP_LEGAL_DOCUMENTS

    def search(self, query: str, *, limit: int) -> list[GlobalSearchResult]:
        results: list[GlobalSearchResult] = []

        for document in legal_document_service.list_all(include_inactive=True):
            regulation_number = legal_document_regulation_number(document)
            searchable_values = (
                document.number,
                document.year,
                document.title,
                document.short_title,
                regulation_number,
            )
            if not contains_query(query, *searchable_values):
                continue

            search_text = " ".join(str(value) for value in searchable_values if value)
            results.append(
                GlobalSearchResult(
                    entity_type=ENTITY_TYPE_LEGAL_DOCUMENT,
                    entity_id=document.id,
                    title=_document_title_label(document),
                    subtitle=RESULT_TYPE_LEGAL_DOCUMENT,
                    search_text=search_text,
                    sort_key=_document_sort_key(document),
                    module_key=self.module_key,
                    group_label=GROUP_LEGAL_DOCUMENTS,
                )
            )

        results.sort(key=lambda item: item.sort_key)
        return results[:limit]
