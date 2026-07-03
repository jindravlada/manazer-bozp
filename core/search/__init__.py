from core.search.bootstrap import build_default_global_search_service
from core.search.global_search_service import GlobalSearchService
from core.search.search_provider import SearchProvider
from core.search.search_result import SearchResult

global_search_service = build_default_global_search_service()

__all__ = [
    "GlobalSearchService",
    "SearchProvider",
    "SearchResult",
    "build_default_global_search_service",
    "global_search_service",
]
