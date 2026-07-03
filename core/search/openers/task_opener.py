"""Otevírání výsledků globálního vyhledávání typu task."""

from __future__ import annotations

from core.search.search_result import SearchResult
from moduly.ukoly.sluzby.task_service import task_service


def open_task_search_result(host, result: SearchResult) -> bool:
    if host is None:
        return False
    if result.source_id <= 0:
        return False

    page_widgets = getattr(host, "_page_widgets", None)
    if not isinstance(page_widgets, dict):
        return False

    page = page_widgets.get("ukoly")
    if page is None:
        return False

    task = task_service.get_task_by_id(result.source_id)
    if task is None:
        return False

    show = getattr(host, "_show", None)
    if callable(show):
        show("ukoly")

    page.open_task(result.source_id)
    return True
