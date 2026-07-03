"""Centrální agregátor globálního vyhledávání."""

from __future__ import annotations

import logging

from core.search.constants import DEFAULT_SEARCH_LIMIT, MIN_QUERY_LENGTH
from core.search.search_provider import SearchProvider
from core.search.search_result import SearchResult
from core.search.search_result_opener import SearchResultOpener
from core.search.search_utils import normalize_query

logger = logging.getLogger(__name__)


class GlobalSearchService:
    def __init__(self, result_opener: SearchResultOpener | None = None) -> None:
        self._providers: list[SearchProvider] = []
        self._result_opener = (
            result_opener if result_opener is not None else SearchResultOpener()
        )

    def register_provider(self, provider: SearchProvider) -> None:
        self._providers.append(provider)

    @property
    def providers(self) -> tuple[SearchProvider, ...]:
        return tuple(self._providers)

    def search(self, text: str, *, limit: int = DEFAULT_SEARCH_LIMIT) -> list[SearchResult]:
        query = normalize_query(text)
        if len(query) < MIN_QUERY_LENGTH:
            return []

        merged: list[SearchResult] = []
        for provider in self._providers:
            try:
                merged.extend(provider.search(query, limit=limit))
            except Exception:
                logger.exception(
                    "Search provider %s failed",
                    getattr(provider, "provider_key", provider.__class__.__name__),
                )

        deduplicated = self._deduplicate(merged)
        deduplicated.sort(
            key=lambda result: (
                -result.priority,
                result.module_label.casefold(),
                result.title.casefold(),
            )
        )
        return deduplicated[:limit]

    def open_result(self, result: SearchResult, host) -> bool:
        return self._result_opener.open(result, host)

    def can_open_result(self, result: SearchResult) -> bool:
        return self._result_opener.can_open(result)

    @staticmethod
    def _deduplicate(results: list[SearchResult]) -> list[SearchResult]:
        best: dict[tuple[str, int], SearchResult] = {}
        for result in results:
            key = (result.source_type, result.source_id)
            existing = best.get(key)
            if existing is None or result.priority > existing.priority:
                best[key] = result
        return list(best.values())
