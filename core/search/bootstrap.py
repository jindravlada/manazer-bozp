"""Sestavení výchozí instance globálního vyhledávání a registrace providerů."""

from core.search.global_search_service import GlobalSearchService
from core.search.providers.task_search_provider import TaskSearchProvider


def build_default_global_search_service() -> GlobalSearchService:
    service = GlobalSearchService()
    service.register_provider(TaskSearchProvider())
    return service
