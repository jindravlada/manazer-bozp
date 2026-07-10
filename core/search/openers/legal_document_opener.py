"""Otevírání výsledků globálního vyhledávání typu legal_document."""

from __future__ import annotations

from core.search.global_search_result import GlobalSearchResult
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service


def open_legal_document_search_result(host, result: GlobalSearchResult) -> bool:
    if host is None or result.entity_id <= 0:
        return False

    page_widgets = getattr(host, "_page_widgets", None)
    if not isinstance(page_widgets, dict):
        return False

    page = page_widgets.get("pravni_pozadavky")
    if page is None:
        return False

    document = legal_document_service.get_by_id(result.entity_id)
    if document is None:
        return False

    show = getattr(host, "_show", None)
    if callable(show):
        show("pravni_pozadavky")

    open_document = getattr(page, "open_document", None)
    if not callable(open_document):
        return False

    open_document(result.entity_id)
    return True
