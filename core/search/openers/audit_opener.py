"""Otevírání výsledků globálního vyhledávání typu audit."""

from __future__ import annotations

from core.search.search_result import SearchResult
from moduly.audity.sluzby.audit_service import audit_service


def open_audit_search_result(host, result: SearchResult) -> bool:
    if host is None:
        return False
    if result.source_id <= 0:
        return False

    page_widgets = getattr(host, "_page_widgets", None)
    if not isinstance(page_widgets, dict):
        return False

    page = page_widgets.get("audity")
    if page is None:
        return False

    audit = audit_service.get_by_id(result.source_id)
    if audit is None:
        return False

    show = getattr(host, "_show", None)
    if callable(show):
        show("audity")

    page.open_audit(result.source_id)
    return True
