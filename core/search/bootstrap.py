"""Sestavení výchozí instance globálního vyhledávání a registrace providerů."""

from core.search.constants import SOURCE_TYPE_TASK
from core.search.global_search_service import GlobalSearchService
from core.search.openers.task_opener import open_task_search_result
from core.search.providers.task_search_provider import TaskSearchProvider
from core.search.search_result_opener import SearchResultOpener


def build_default_search_result_opener() -> SearchResultOpener:
    opener = SearchResultOpener()
    opener.register(SOURCE_TYPE_TASK, open_task_search_result)
    return opener


def build_default_global_search_service() -> GlobalSearchService:
    service = GlobalSearchService(result_opener=build_default_search_result_opener())
    service.register_provider(TaskSearchProvider())
    return service
