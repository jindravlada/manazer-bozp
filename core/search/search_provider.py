"""Rozhraní poskytovatele výsledků globálního vyhledávání."""

from abc import ABC, abstractmethod

from core.search.global_search_result import GlobalSearchResult


class SearchProvider(ABC):
    provider_key: str
    module_key: str
    module_label: str

    @abstractmethod
    def search(self, query: str, *, limit: int) -> list[GlobalSearchResult]:
        """Vyhledá záznamy odpovídající dotazu."""
