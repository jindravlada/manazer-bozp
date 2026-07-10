"""Otevírání výsledků globálního vyhledávání typu legal_requirement."""

from __future__ import annotations

from core.search.global_search_result import GlobalSearchResult
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service


def open_legal_requirement_search_result(host, result: GlobalSearchResult) -> bool:
    if host is None or result.entity_id <= 0:
        return False

    page_widgets = getattr(host, "_page_widgets", None)
    if not isinstance(page_widgets, dict):
        return False

    page = page_widgets.get("pravni_pozadavky")
    if page is None:
        return False

    requirement = legal_requirement_service.get_by_id(result.entity_id)
    if requirement is None:
        return False

    show = getattr(host, "_show", None)
    if callable(show):
        show("pravni_pozadavky")

    open_requirement = getattr(page, "open_requirement", None)
    if not callable(open_requirement):
        return False

    open_requirement(result.entity_id)
    return True
