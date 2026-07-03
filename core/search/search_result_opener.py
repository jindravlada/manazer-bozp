"""Registr handlerů pro otevírání výsledků globálního vyhledávání."""

from __future__ import annotations

import logging
from collections.abc import Callable

from core.search.search_result import SearchResult

logger = logging.getLogger(__name__)

OpenHandler = Callable[[object, SearchResult], bool]


class SearchResultOpener:
    def __init__(self) -> None:
        self._handlers: dict[str, OpenHandler] = {}

    def register(self, source_type: str, handler: OpenHandler) -> None:
        self._handlers[source_type] = handler

    def can_open(self, result: SearchResult) -> bool:
        return result.source_type in self._handlers

    def open(self, result: SearchResult, host) -> bool:
        handler = self._handlers.get(result.source_type)
        if handler is None:
            return False

        try:
            return bool(handler(host, result))
        except Exception:
            logger.exception(
                "Failed to open search result %s/%s",
                result.source_type,
                result.source_id,
            )
            return False
