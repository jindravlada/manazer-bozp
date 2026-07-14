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
TAB_PHOTOS = "Fotodokumentace"
TAB_INVENTORY = "Analýza pracoviště"
TAB_EVENTS = "Nežádoucí události"  # odstraněno z dialogu ve fázi R15 (UI sloučeno do Analýzy)
TAB_RISK_ASSESSMENT = "Posouzení rizik"
TAB_AI_PEER_REVIEW = "Oponentní posouzení AI"
TAB_MEASURES = "Opatření"
TAB_PUBLICATION = "Publikace"
TAB_HISTORY = "Historie"

# Zpětná kompatibilita se starším názvem záložky.
TAB_AI_CONSULTATION = TAB_AI_PEER_REVIEW
# Odstraněno v R12 (entita Nebezpečí).
TAB_HAZARDS = "Nebezpečí"

HAZARD_IDENTIFICATION_TABS = (
    TAB_BASICS,
    TAB_PHOTOS,
    TAB_INVENTORY,
    TAB_RISK_ASSESSMENT,
    TAB_AI_PEER_REVIEW,
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

WORKPLACE_ANALYSIS_SELECT_ITEM = "Vyberte položku analýzy pracoviště."

WORKPLACE_ANALYSIS_READ_ONLY_MESSAGE = (
    "Analýza pracoviště je u dokončené nebo archivované identifikace pouze pro čtení."
)


def is_identification_inventory_read_only(status: str) -> bool:
    return status in READ_ONLY_IDENTIFICATION_STATUSES


PHOTOS_INTRO_TEXT = (
    "Tato fotodokumentace zachycuje skutečný stav pracoviště v době provádění "
    "identifikace rizik. Slouží jako pracovní podklad i jako důkaz, že identifikace "
    "byla provedena na místě."
)

HAZARD_PHOTO_DIALOG_TITLE = "Fotografie identifikace"
HAZARD_PHOTO_MISSING_FILE_MESSAGE = (
    "Soubor fotografie nebyl nalezen. Záznam zůstává v evidenci, "
    "ale náhled nelze zobrazit."
)

PHOTO_COL_ID = 0
PHOTO_COL_THUMBNAIL = 1
PHOTO_COL_CAPTION = 2
PHOTO_COL_TAKEN_AT = 3
PHOTO_COL_SIZE = 4
PHOTO_COL_ACTIVE = 5
PHOTO_COLUMN_COUNT = 6

PHOTO_TABLE_HEADERS = [
    "ID",
    "Náhled",
    "Popis",
    "Datum pořízení",
    "Velikost",
    "Aktivní",
]


def is_identification_photos_read_only(status: str) -> bool:
    return status in READ_ONLY_IDENTIFICATION_STATUSES


def format_photo_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def is_identification_events_read_only(status: str) -> bool:
    return status in READ_ONLY_IDENTIFICATION_STATUSES


EVENTS_INTRO_TEXT = (
    "Popište konkrétní nežádoucí události příslušné k jednotlivým zdrojům analýzy pracoviště."
)

HAZARD_EVENT_DIALOG_TITLE = "Nežádoucí událost"

EVENT_COL_ID = 0
EVENT_COL_NAME = 1
EVENT_COL_INVENTORY_ITEM = 2
EVENT_COL_ACTIVE = 3
EVENT_COLUMN_COUNT = 4

EVENT_TABLE_HEADERS = [
    "ID",
    "Nežádoucí událost",
    "Zdroj analýzy",
    "Aktivní",
]

# Tabulka událostí v záložce Analýza pracoviště (bez sloupce Zdroj analýzy).
ITEM_EVENT_COL_ID = 0
ITEM_EVENT_COL_NAME = 1
ITEM_EVENT_COL_ACTIVE = 2
ITEM_EVENT_COLUMN_COUNT = 3
ITEM_EVENT_TABLE_HEADERS = ["ID", "Nežádoucí událost", "Aktivní"]

ITEM_EVENTS_SELECT_ITEM = "Vyberte položku analýzy pracoviště."
ITEM_EVENTS_SELECT_EVENT = "Vyberte nežádoucí událost."
ITEM_EVENTS_SECTION_TITLE = "Nežádoucí události vybrané položky"


def format_event_display_name(name: str, *, assessment_count: int = 0) -> str:
    if not assessment_count:
        return name
    suffix = "posouzení" if assessment_count == 1 else "posouzení"
    return f"{name} — {assessment_count} {suffix}"


def format_risk_assessment_display_name(
    exposed_group: str,
    *,
    assessment_status_label: str | None = None,
    existing_measure_count: int = 0,
    required_measure_count: int = 0,
) -> str:
    parts = [exposed_group]
    if assessment_status_label:
        parts.append(assessment_status_label)
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


def format_risk_assessment_completed_at(value) -> str:
    if value is None:
        return ""
    return value.strftime("%d.%m.%Y")


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
RISK_ASSESSMENT_COL_INVENTORY_ITEM = 3
RISK_ASSESSMENT_COL_CONSEQUENCE = 4
RISK_ASSESSMENT_COL_SEVERITY = 5
RISK_ASSESSMENT_COL_STATUS = 6
RISK_ASSESSMENT_COL_COMPLETED_AT = 7
RISK_ASSESSMENT_COL_ACTIVE = 8
RISK_ASSESSMENT_COLUMN_COUNT = 9

RISK_ASSESSMENT_TABLE_HEADERS = [
    "ID",
    "Ohrožená skupina",
    "Nežádoucí událost",
    "Zdroj analýzy",
    "Možný následek",
    "Závažnost",
    "Stav posouzení",
    "Dokončeno dne",
    "Aktivní",
]

RISK_ASSESSMENT_STATUS_DRAFT = "draft"
RISK_ASSESSMENT_STATUS_COMPLETED = "completed"

RISK_ASSESSMENT_STATUSES = (
    RISK_ASSESSMENT_STATUS_DRAFT,
    RISK_ASSESSMENT_STATUS_COMPLETED,
)

DEFAULT_RISK_ASSESSMENT_STATUS = RISK_ASSESSMENT_STATUS_DRAFT

RISK_ASSESSMENT_STATUS_LABELS = {
    RISK_ASSESSMENT_STATUS_DRAFT: "Rozpracováno",
    RISK_ASSESSMENT_STATUS_COMPLETED: "Dokončeno",
}


def format_risk_assessment_status_label(status: str) -> str:
    return RISK_ASSESSMENT_STATUS_LABELS.get(status, status or "—")


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
    event_count: int = 0,
) -> str:
    if not event_count:
        return name
    suffix = "událost" if event_count == 1 else "událostí"
    return f"{name} — {event_count} {suffix}"
