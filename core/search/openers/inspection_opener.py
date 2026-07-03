"""Otevírání výsledků globálního vyhledávání typu inspection."""

from __future__ import annotations

from core.search.search_result import SearchResult
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service


def open_inspection_search_result(host, result: SearchResult) -> bool:
    if host is None:
        return False
    if result.source_id <= 0:
        return False

    page_widgets = getattr(host, "_page_widgets", None)
    if not isinstance(page_widgets, dict):
        return False

    page = page_widgets.get("proverky")
    if page is None:
        return False

    inspection = bozp_inspection_service.get_by_id(result.source_id)
    if inspection is None:
        return False

    show = getattr(host, "_show", None)
    if callable(show):
        show("proverky")

    page.open_inspection(result.source_id)
    return True
