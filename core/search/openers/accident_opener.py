"""Otevírání výsledků globálního vyhledávání typu accident."""

from __future__ import annotations

from core.search.search_result import SearchResult
from moduly.kniha_urazu.sluzby.accident_service import accident_service


def open_accident_search_result(host, result: SearchResult) -> bool:
    if host is None:
        return False
    if result.source_id <= 0:
        return False

    page_widgets = getattr(host, "_page_widgets", None)
    if not isinstance(page_widgets, dict):
        return False

    page = page_widgets.get("kniha_urazu")
    if page is None:
        return False

    accident = accident_service.get_by_id(result.source_id)
    if accident is None:
        return False

    show = getattr(host, "_show", None)
    if callable(show):
        show("kniha_urazu")

    page.open_accident(result.source_id)
    return True
