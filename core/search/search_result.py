"""Zpětná kompatibilita s dřívějším názvem modelu výsledku."""

from core.search.global_search_result import GlobalSearchResult

SearchResult = GlobalSearchResult

__all__ = ["GlobalSearchResult", "SearchResult"]
