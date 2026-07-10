"""Konstanty globálního vyhledávání."""

MIN_QUERY_LENGTH = 2
DEFAULT_SEARCH_LIMIT = 30

SOURCE_TYPE_TASK = "task"
SOURCE_TYPE_AUDIT = "audit"
SOURCE_TYPE_INSPECTION = "inspection"
SOURCE_TYPE_ACCIDENT = "accident"
SOURCE_TYPE_ACTION = "action"

ENTITY_TYPE_LEGAL_REQUIREMENT = "legal_requirement"
ENTITY_TYPE_LEGAL_DOCUMENT = "legal_document"

GROUP_LEGAL_REQUIREMENTS = "Řídicí procesy"
GROUP_LEGAL_DOCUMENTS = "Právní předpisy"

RESULT_TYPE_LEGAL_REQUIREMENT = "Řídicí proces"
RESULT_TYPE_LEGAL_DOCUMENT = "Právní předpis"

GROUP_SORT_ORDER = {
    GROUP_LEGAL_REQUIREMENTS: 0,
    GROUP_LEGAL_DOCUMENTS: 1,
    "Úkoly": 10,
    "Audity": 11,
    "Prověrky BOZP": 12,
    "Kniha úrazů": 13,
}
