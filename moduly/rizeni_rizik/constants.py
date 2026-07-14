"""Konstanty modulu Řízení rizik."""

MODULE_KEY = "rizeni_rizik"
MODULE_NAME = "Řízení rizik"
MODULE_DESCRIPTION = "Identifikace nebezpečí a řízení rizik na provozech a pracovištích."

HAZARD_IDENTIFICATION_STATUS_DRAFT = "draft"
HAZARD_IDENTIFICATION_STATUS_IN_PROGRESS = "in_progress"
HAZARD_IDENTIFICATION_STATUS_COMPLETED = "completed"
HAZARD_IDENTIFICATION_STATUS_ARCHIVED = "archived"

HAZARD_IDENTIFICATION_STATUSES = (
    HAZARD_IDENTIFICATION_STATUS_DRAFT,
    HAZARD_IDENTIFICATION_STATUS_IN_PROGRESS,
    HAZARD_IDENTIFICATION_STATUS_COMPLETED,
    HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
)

DEFAULT_HAZARD_IDENTIFICATION_STATUS = HAZARD_IDENTIFICATION_STATUS_DRAFT

HAZARD_IDENTIFICATION_STATUS_LABELS = {
    HAZARD_IDENTIFICATION_STATUS_DRAFT: "Koncept",
    HAZARD_IDENTIFICATION_STATUS_IN_PROGRESS: "Probíhá",
    HAZARD_IDENTIFICATION_STATUS_COMPLETED: "Dokončeno",
    HAZARD_IDENTIFICATION_STATUS_ARCHIVED: "Archivováno",
}

COL_ID = 0
COL_IDENTIFICATION = 1
COL_OPERATION = 2
COL_WORKPLACE = 3
COL_STARTED_AT = 4
COL_RESPONSIBLE_PERSON = 5
COL_STATUS = 6
COLUMN_COUNT = 7

TABLE_HEADERS = [
    "ID",
    "Identifikace",
    "Provoz",
    "Pracoviště",
    "Datum zahájení",
    "Odpovědná osoba",
    "Stav",
]

TAB_BASICS = "Základní údaje"
TAB_INVENTORY = "Analýza pracoviště"
TAB_HAZARDS = "Nebezpečí"
TAB_EVENTS = "Nežádoucí události"
TAB_RISK_ASSESSMENT = "Posouzení rizik"
TAB_MEASURES = "Opatření"
TAB_PUBLICATION = "Publikace"
TAB_HISTORY = "Historie"

HAZARD_IDENTIFICATION_TABS = (
    TAB_BASICS,
    TAB_INVENTORY,
    TAB_HAZARDS,
    TAB_EVENTS,
    TAB_RISK_ASSESSMENT,
    TAB_MEASURES,
    TAB_PUBLICATION,
    TAB_HISTORY,
)

DIALOG_WINDOW_TITLE = "Identifikace nebezpečí"

INVENTORY_INTRO_TEXT = (
    "Popište pracoviště – zaznamenejte zařízení, činnosti, energie, látky, prostory, "
    "dopravu, osoby, podmínky prostředí a další skutečnosti, které se zde vyskytují."
)

HAZARD_INVENTORY_CATEGORY_EQUIPMENT = "equipment"
HAZARD_INVENTORY_CATEGORY_ACTIVITY = "activity"
HAZARD_INVENTORY_CATEGORY_ENERGY = "energy"
HAZARD_INVENTORY_CATEGORY_SUBSTANCE = "substance"
HAZARD_INVENTORY_CATEGORY_STRUCTURE = "structure"
HAZARD_INVENTORY_CATEGORY_TRANSPORT = "transport"
HAZARD_INVENTORY_CATEGORY_PERSON = "person"
HAZARD_INVENTORY_CATEGORY_ENVIRONMENT = "environment"
HAZARD_INVENTORY_CATEGORY_OTHER = "other"

HAZARD_INVENTORY_CATEGORIES = (
    HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
    HAZARD_INVENTORY_CATEGORY_ACTIVITY,
    HAZARD_INVENTORY_CATEGORY_ENERGY,
    HAZARD_INVENTORY_CATEGORY_SUBSTANCE,
    HAZARD_INVENTORY_CATEGORY_STRUCTURE,
    HAZARD_INVENTORY_CATEGORY_TRANSPORT,
    HAZARD_INVENTORY_CATEGORY_PERSON,
    HAZARD_INVENTORY_CATEGORY_ENVIRONMENT,
    HAZARD_INVENTORY_CATEGORY_OTHER,
)

HAZARD_INVENTORY_CATEGORY_LABELS = {
    HAZARD_INVENTORY_CATEGORY_EQUIPMENT: "Stroje a zařízení",
    HAZARD_INVENTORY_CATEGORY_ACTIVITY: "Činnosti",
    HAZARD_INVENTORY_CATEGORY_ENERGY: "Energie",
    HAZARD_INVENTORY_CATEGORY_SUBSTANCE: "Látky a materiály",
    HAZARD_INVENTORY_CATEGORY_STRUCTURE: "Prostory a konstrukce",
    HAZARD_INVENTORY_CATEGORY_TRANSPORT: "Doprava",
    HAZARD_INVENTORY_CATEGORY_PERSON: "Osoby",
    HAZARD_INVENTORY_CATEGORY_ENVIRONMENT: "Podmínky prostředí",
    HAZARD_INVENTORY_CATEGORY_OTHER: "Ostatní",
}

READ_ONLY_IDENTIFICATION_STATUSES = (
    HAZARD_IDENTIFICATION_STATUS_COMPLETED,
    HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
)

INVENTORY_ITEM_DIALOG_TITLE = "Položka analýzy pracoviště"

INVENTORY_COL_ID = 0
INVENTORY_COL_NAME = 1
INVENTORY_COL_DESCRIPTION = 2
INVENTORY_COL_ACTIVE = 3
INVENTORY_COLUMN_COUNT = 4

INVENTORY_TABLE_HEADERS = ["ID", "Název", "Popis", "Aktivní"]

HAZARD_INVENTORY_RELATION_ACTIVITY = "activity"
HAZARD_INVENTORY_RELATION_ENERGY = "energy"
HAZARD_INVENTORY_RELATION_SUBSTANCE = "substance"
HAZARD_INVENTORY_RELATION_PERSON = "person"
HAZARD_INVENTORY_RELATION_ENVIRONMENT = "environment"
HAZARD_INVENTORY_RELATION_TRANSPORT = "transport"
HAZARD_INVENTORY_RELATION_STRUCTURE = "structure"
HAZARD_INVENTORY_RELATION_EQUIPMENT = "equipment"
HAZARD_INVENTORY_RELATION_OTHER = "other"

HAZARD_INVENTORY_RELATION_TYPES = (
    HAZARD_INVENTORY_RELATION_ACTIVITY,
    HAZARD_INVENTORY_RELATION_ENERGY,
    HAZARD_INVENTORY_RELATION_SUBSTANCE,
    HAZARD_INVENTORY_RELATION_PERSON,
    HAZARD_INVENTORY_RELATION_ENVIRONMENT,
    HAZARD_INVENTORY_RELATION_TRANSPORT,
    HAZARD_INVENTORY_RELATION_STRUCTURE,
    HAZARD_INVENTORY_RELATION_EQUIPMENT,
    HAZARD_INVENTORY_RELATION_OTHER,
)

HAZARD_INVENTORY_RELATION_TYPE_LABELS = {
    HAZARD_INVENTORY_RELATION_ACTIVITY: "Související činnost",
    HAZARD_INVENTORY_RELATION_ENERGY: "Související energie",
    HAZARD_INVENTORY_RELATION_SUBSTANCE: "Související látka nebo materiál",
    HAZARD_INVENTORY_RELATION_PERSON: "Ohrožená / přítomná osoba",
    HAZARD_INVENTORY_RELATION_ENVIRONMENT: "Podmínka prostředí",
    HAZARD_INVENTORY_RELATION_TRANSPORT: "Související doprava",
    HAZARD_INVENTORY_RELATION_STRUCTURE: "Související prostor nebo konstrukce",
    HAZARD_INVENTORY_RELATION_EQUIPMENT: "Související zařízení",
    HAZARD_INVENTORY_RELATION_OTHER: "Jiná souvislost",
}

HAZARD_INVENTORY_RELATION_TARGET_CATEGORY = {
    HAZARD_INVENTORY_RELATION_ACTIVITY: HAZARD_INVENTORY_CATEGORY_ACTIVITY,
    HAZARD_INVENTORY_RELATION_ENERGY: HAZARD_INVENTORY_CATEGORY_ENERGY,
    HAZARD_INVENTORY_RELATION_SUBSTANCE: HAZARD_INVENTORY_CATEGORY_SUBSTANCE,
    HAZARD_INVENTORY_RELATION_PERSON: HAZARD_INVENTORY_CATEGORY_PERSON,
    HAZARD_INVENTORY_RELATION_ENVIRONMENT: HAZARD_INVENTORY_CATEGORY_ENVIRONMENT,
    HAZARD_INVENTORY_RELATION_TRANSPORT: HAZARD_INVENTORY_CATEGORY_TRANSPORT,
    HAZARD_INVENTORY_RELATION_STRUCTURE: HAZARD_INVENTORY_CATEGORY_STRUCTURE,
    HAZARD_INVENTORY_RELATION_EQUIPMENT: HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
    HAZARD_INVENTORY_RELATION_OTHER: HAZARD_INVENTORY_CATEGORY_OTHER,
}

INVENTORY_ANALYSIS_TITLE = "Analýza položky"
INVENTORY_RELATION_DIALOG_TITLE = "Souvislost analýzy pracoviště"

RELATION_COL_ID = 0
RELATION_COL_TYPE = 1
RELATION_COL_CATEGORY = 2
RELATION_COL_NAME = 3
RELATION_COL_NOTE = 4
RELATION_COL_ACTIVE = 5
RELATION_COLUMN_COUNT = 6

RELATION_TABLE_HEADERS = [
    "ID",
    "Typ souvislosti",
    "Kategorie",
    "Název",
    "Poznámka",
    "Aktivní",
]


def inventory_relation_target_category(relation_type: str) -> str | None:
    return HAZARD_INVENTORY_RELATION_TARGET_CATEGORY.get(relation_type)


WORKPLACE_ANALYSIS_SELECT_ITEM = "Vyberte položku analýzy pracoviště."

WORKPLACE_ANALYSIS_READ_ONLY_MESSAGE = (
    "Analýza pracoviště je u dokončené nebo archivované identifikace pouze pro čtení."
)


def is_identification_inventory_read_only(status: str) -> bool:
    return status in READ_ONLY_IDENTIFICATION_STATUSES


IDENTIFIED_HAZARD_SOURCE_MANUAL = "manual"
IDENTIFIED_HAZARD_SOURCE_LIBRARY = "library"
IDENTIFIED_HAZARD_SOURCE_AI = "ai"
IDENTIFIED_HAZARD_SOURCE_AUDIT = "audit"
IDENTIFIED_HAZARD_SOURCE_INSPECTION = "inspection"
IDENTIFIED_HAZARD_SOURCE_ACCIDENT = "accident"
IDENTIFIED_HAZARD_SOURCE_LEGAL_CHANGE = "legal_change"
IDENTIFIED_HAZARD_SOURCE_OTHER = "other"

IDENTIFIED_HAZARD_SOURCE_TYPES = (
    IDENTIFIED_HAZARD_SOURCE_MANUAL,
    IDENTIFIED_HAZARD_SOURCE_LIBRARY,
    IDENTIFIED_HAZARD_SOURCE_AI,
    IDENTIFIED_HAZARD_SOURCE_AUDIT,
    IDENTIFIED_HAZARD_SOURCE_INSPECTION,
    IDENTIFIED_HAZARD_SOURCE_ACCIDENT,
    IDENTIFIED_HAZARD_SOURCE_LEGAL_CHANGE,
    IDENTIFIED_HAZARD_SOURCE_OTHER,
)

DEFAULT_IDENTIFIED_HAZARD_SOURCE = IDENTIFIED_HAZARD_SOURCE_MANUAL

IDENTIFIED_HAZARD_SOURCE_LABELS = {
    IDENTIFIED_HAZARD_SOURCE_MANUAL: "Ručně",
    IDENTIFIED_HAZARD_SOURCE_LIBRARY: "Firemní knihovna",
    IDENTIFIED_HAZARD_SOURCE_AI: "Návrh AI",
    IDENTIFIED_HAZARD_SOURCE_AUDIT: "Audit",
    IDENTIFIED_HAZARD_SOURCE_INSPECTION: "Prověrka",
    IDENTIFIED_HAZARD_SOURCE_ACCIDENT: "Pracovní úraz",
    IDENTIFIED_HAZARD_SOURCE_LEGAL_CHANGE: "Změna legislativy",
    IDENTIFIED_HAZARD_SOURCE_OTHER: "Jiný zdroj",
}

HAZARDS_INTRO_TEXT = (
    "Evidujte nebezpečí zjištěná u jednotlivých položek analýzy pracoviště. "
    "V této fázi se ještě neposuzuje míra rizika ani se neurčují opatření."
)

IDENTIFIED_HAZARD_DIALOG_TITLE = "Nebezpečí"

HAZARD_COL_ID = 0
HAZARD_COL_NAME = 1
HAZARD_COL_INVENTORY_ITEM = 2
HAZARD_COL_INVENTORY_CATEGORY = 3
HAZARD_COL_SOURCE = 4
HAZARD_COL_ACTIVE = 5
HAZARD_COLUMN_COUNT = 6

HAZARD_TABLE_HEADERS = [
    "ID",
    "Nebezpečí",
    "Zdrojová položka analýzy",
    "Kategorie položky analýzy",
    "Původ",
    "Aktivní",
]


def is_identification_hazards_read_only(status: str) -> bool:
    return status in READ_ONLY_IDENTIFICATION_STATUSES


def is_identification_hazards_read_only(status: str) -> bool:
    return status in READ_ONLY_IDENTIFICATION_STATUSES


def is_identification_events_read_only(status: str) -> bool:
    return status in READ_ONLY_IDENTIFICATION_STATUSES


EVENTS_INTRO_TEXT = (
    "Popište konkrétní nežádoucí události, které mohou vzniknout z jednotlivých nebezpečí."
)

HAZARD_EVENT_DIALOG_TITLE = "Nežádoucí událost"

EVENT_COL_ID = 0
EVENT_COL_NAME = 1
EVENT_COL_HAZARD = 2
EVENT_COL_INVENTORY_ITEM = 3
EVENT_COL_ACTIVE = 4
EVENT_COLUMN_COUNT = 5

EVENT_TABLE_HEADERS = [
    "ID",
    "Nežádoucí událost",
    "Nebezpečí",
    "Zdrojová položka analýzy",
    "Aktivní",
]


def format_hazard_display_name(name: str, *, event_count: int = 0) -> str:
    if not event_count:
        return name
    suffix = "událost" if event_count == 1 else "události"
    return f"{name} — {event_count} {suffix}"


def format_event_display_name(name: str, *, assessment_count: int = 0) -> str:
    if not assessment_count:
        return name
    suffix = "posouzení" if assessment_count == 1 else "posouzení"
    return f"{name} — {assessment_count} {suffix}"


def format_risk_assessment_display_name(
    exposed_group: str,
    *,
    existing_measure_count: int = 0,
    required_measure_count: int = 0,
) -> str:
    parts = [exposed_group]
    if existing_measure_count:
        suffix = (
            "existující opatření"
            if existing_measure_count == 1
            else "existujících opatření"
        )
        parts.append(f"{existing_measure_count} {suffix}")
    if required_measure_count:
        suffix = (
            "potřebné opatření"
            if required_measure_count == 1
            else "potřebná opatření"
        )
        parts.append(f"{required_measure_count} {suffix}")
    if len(parts) == 1:
        return exposed_group
    return " — ".join(parts)


RISK_ASSESSMENTS_INTRO_TEXT = (
    "Určete, které skupiny osob mohou být vystaveny jednotlivým nežádoucím událostem "
    "a popište možný následek včetně jeho závažnosti."
)

HAZARD_RISK_ASSESSMENT_DIALOG_TITLE = "Posouzení rizika"

RISK_SEVERITY_NEGLIGIBLE = "negligible"
RISK_SEVERITY_MINOR = "minor"
RISK_SEVERITY_MODERATE = "moderate"
RISK_SEVERITY_SERIOUS = "serious"
RISK_SEVERITY_CRITICAL = "critical"

RISK_SEVERITIES = (
    RISK_SEVERITY_NEGLIGIBLE,
    RISK_SEVERITY_MINOR,
    RISK_SEVERITY_MODERATE,
    RISK_SEVERITY_SERIOUS,
    RISK_SEVERITY_CRITICAL,
)

DEFAULT_RISK_SEVERITY = RISK_SEVERITY_MODERATE

RISK_SEVERITY_LABELS = {
    RISK_SEVERITY_NEGLIGIBLE: "Zanedbatelný",
    RISK_SEVERITY_MINOR: "Lehký",
    RISK_SEVERITY_MODERATE: "Závažný",
    RISK_SEVERITY_SERIOUS: "Velmi závažný",
    RISK_SEVERITY_CRITICAL: "Kritický",
}

RISK_SEVERITY_DESCRIPTIONS = {
    RISK_SEVERITY_NEGLIGIBLE: (
        "Bez zranění nebo pouze přechodné drobné obtíže bez potřeby odborného ošetření."
    ),
    RISK_SEVERITY_MINOR: (
        "Lehké zranění nebo zdravotní obtíže bez pracovní neschopnosti."
    ),
    RISK_SEVERITY_MODERATE: (
        "Zranění nebo poškození zdraví s pracovní neschopností."
    ),
    RISK_SEVERITY_SERIOUS: (
        "Těžké zranění, hospitalizace, trvalé následky nebo nemoc z povolání."
    ),
    RISK_SEVERITY_CRITICAL: (
        "Smrtelné zranění nebo událost s možností postižení více osob."
    ),
}


def format_risk_severity_label(severity: str) -> str:
    return RISK_SEVERITY_LABELS.get(severity, severity or "—")


RISK_ASSESSMENT_COL_ID = 0
RISK_ASSESSMENT_COL_EXPOSED_GROUP = 1
RISK_ASSESSMENT_COL_EVENT = 2
RISK_ASSESSMENT_COL_HAZARD = 3
RISK_ASSESSMENT_COL_CONSEQUENCE = 4
RISK_ASSESSMENT_COL_SEVERITY = 5
RISK_ASSESSMENT_COL_ACTIVE = 6
RISK_ASSESSMENT_COLUMN_COUNT = 7

RISK_ASSESSMENT_TABLE_HEADERS = [
    "ID",
    "Ohrožená skupina",
    "Nežádoucí událost",
    "Nebezpečí",
    "Možný následek",
    "Závažnost",
    "Aktivní",
]


def is_identification_risk_assessment_read_only(status: str) -> bool:
    return status in READ_ONLY_IDENTIFICATION_STATUSES


EXISTING_MEASURES_TITLE = "Existující opatření"
HAZARD_EXISTING_MEASURE_DIALOG_TITLE = "Existující opatření"
EXISTING_MEASURE_SELECT_ASSESSMENT = "Vyberte posouzení rizika."

EXISTING_MEASURE_COL_ID = 0
EXISTING_MEASURE_COL_DESCRIPTION = 1
EXISTING_MEASURE_COL_NOTE = 2
EXISTING_MEASURE_COL_ACTIVE = 3
EXISTING_MEASURE_COLUMN_COUNT = 4

EXISTING_MEASURE_TABLE_HEADERS = ["ID", "Opatření", "Poznámka", "Aktivní"]

REQUIRED_MEASURES_TITLE = "Potřebná další opatření"
HAZARD_REQUIRED_MEASURE_DIALOG_TITLE = "Potřebné opatření"
REQUIRED_MEASURE_SELECT_ASSESSMENT = "Vyberte posouzení rizika."

REQUIRED_MEASURE_COL_ID = 0
REQUIRED_MEASURE_COL_DESCRIPTION = 1
REQUIRED_MEASURE_COL_NOTE = 2
REQUIRED_MEASURE_COL_ACTIVE = 3
REQUIRED_MEASURE_COLUMN_COUNT = 4

REQUIRED_MEASURE_TABLE_HEADERS = ["ID", "Opatření", "Poznámka", "Aktivní"]


def format_inventory_item_display_name(
    name: str,
    *,
    relation_count: int = 0,
    hazard_count: int = 0,
) -> str:
    parts = [name]
    if relation_count:
        suffix = "souvislost" if relation_count == 1 else "souvislostí"
        parts.append(f"{relation_count} {suffix}")
    if hazard_count:
        parts.append(f"{hazard_count} nebezpečí")
    if len(parts) == 1:
        return name
    return f"{parts[0]} — " + " — ".join(parts[1:])
