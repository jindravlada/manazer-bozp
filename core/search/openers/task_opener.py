"""Otevírání výsledků globálního vyhledávání typu task."""

from __future__ import annotations

from core.search.global_search_result import GlobalSearchResult
from moduly.ukoly.sluzby.task_service import task_service


def open_task_search_result(host, result: GlobalSearchResult) -> bool:
    if host is None:
        return False
    if result.entity_id <= 0:
        return False

    page_widgets = getattr(host, "_page_widgets", None)
    if not isinstance(page_widgets, dict):
        return False

    page = page_widgets.get("agenda")
    if page is None:
        return False

    task = task_service.get_task_by_id(result.entity_id)
    if task is None:
        return False

    show = getattr(host, "_show", None)
    if callable(show):
        show("agenda")

    page.open_task(result.entity_id)
    return True
