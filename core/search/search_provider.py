"""Rozhraní poskytovatele výsledků globálního vyhledávání."""

from abc import ABC, abstractmethod

from core.search.search_result import SearchResult


class SearchProvider(ABC):
    provider_key: str
    module_key: str
    module_label: str

    @abstractmethod
    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        """Vyhledá záznamy odpovídající dotazu."""
