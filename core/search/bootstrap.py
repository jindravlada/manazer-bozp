"""Sestavení výchozí instance globálního vyhledávání a registrace providerů."""

from core.search.constants import (
    ENTITY_TYPE_LEGAL_DOCUMENT,
    ENTITY_TYPE_LEGAL_REQUIREMENT,
    SOURCE_TYPE_ACCIDENT,
    SOURCE_TYPE_AUDIT,
    SOURCE_TYPE_INSPECTION,
    SOURCE_TYPE_TASK,
)
from core.search.global_search_service import GlobalSearchService
from core.search.openers.accident_opener import open_accident_search_result
from core.search.openers.audit_opener import open_audit_search_result
from core.search.openers.inspection_opener import open_inspection_search_result
from core.search.openers.legal_document_opener import open_legal_document_search_result
from core.search.openers.legal_requirement_opener import open_legal_requirement_search_result
from core.search.openers.task_opener import open_task_search_result
from core.search.providers.accident_search_provider import AccidentSearchProvider
from core.search.providers.audit_search_provider import AuditSearchProvider
from core.search.providers.legal_document_search_provider import LegalDocumentSearchProvider
from core.search.providers.legal_requirement_search_provider import LegalRequirementSearchProvider
from core.search.providers.proverky_search_provider import ProverkySearchProvider
from core.search.providers.task_search_provider import TaskSearchProvider
from core.search.search_result_opener import SearchResultOpener


def build_default_search_result_opener() -> SearchResultOpener:
    opener = SearchResultOpener()
    opener.register(ENTITY_TYPE_LEGAL_REQUIREMENT, open_legal_requirement_search_result)
    opener.register(ENTITY_TYPE_LEGAL_DOCUMENT, open_legal_document_search_result)
    opener.register(SOURCE_TYPE_TASK, open_task_search_result)
    opener.register(SOURCE_TYPE_AUDIT, open_audit_search_result)
    opener.register(SOURCE_TYPE_INSPECTION, open_inspection_search_result)
    opener.register(SOURCE_TYPE_ACCIDENT, open_accident_search_result)
    return opener


def build_default_global_search_service() -> GlobalSearchService:
    service = GlobalSearchService(result_opener=build_default_search_result_opener())
    service.register_provider(LegalRequirementSearchProvider())
    service.register_provider(LegalDocumentSearchProvider())
    service.register_provider(TaskSearchProvider())
    service.register_provider(AuditSearchProvider())
    service.register_provider(ProverkySearchProvider())
    service.register_provider(AccidentSearchProvider())
    return service
