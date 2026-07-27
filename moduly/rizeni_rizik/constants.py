"""Konstanty modulu Řízení rizik."""

from core.shared.risk_severity import (
    DEFAULT_RISK_SEVERITY,
    RISK_SEVERITIES,
    RISK_SEVERITY_CRITICAL,
    RISK_SEVERITY_DESCRIPTIONS,
    RISK_SEVERITY_LABELS,
    RISK_SEVERITY_MINOR,
    RISK_SEVERITY_MODERATE,
    RISK_SEVERITY_NEGLIGIBLE,
    RISK_SEVERITY_SERIOUS,
    format_risk_severity_description,
    format_risk_severity_label,
    format_risk_severity_tooltip,
)

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
COL_WORKPLACE_PART = 4
COL_STARTED_AT = 5
COL_RESPONSIBLE_PERSON = 6
COL_STATUS = 7
COLUMN_COUNT = 8

TABLE_HEADERS = [
    "ID",
    "Identifikace",
    "Provoz",
    "Pracoviště",
    "Část pracoviště",
    "Datum zahájení",
    "Odpovědná osoba",
    "Stav",
]

TAB_BASICS = "Základní údaje"
TAB_PHOTOS = "Fotodokumentace"
TAB_INVENTORY = "Zdroje rizik na pracovišti"
TAB_EVENTS = "Nežádoucí události"  # odstraněno z dialogu ve fázi R15 (UI sloučeno do zdrojů rizik)
TAB_RISK_ASSESSMENT = "Posouzení zdrojů rizik"
TAB_AI_PEER_REVIEW = "Oponentní posouzení AI"  # R21a: skryto v Identifikaci (AI jen v Katalogu)
TAB_MEASURES = "Opatření"  # R21a: dočasně nezobrazeno
TAB_PUBLICATION = "Publikace"  # R21a: dočasně nezobrazeno
TAB_HISTORY = "Historie"  # R21a: dočasně nezobrazeno

# Zpětná kompatibilita se starším názvem záložky.
TAB_AI_CONSULTATION = TAB_AI_PEER_REVIEW
# Odstraněno v R12 (entita Nebezpečí).
TAB_HAZARDS = "Nebezpečí"

# Plný seznam záložek včetně skrytých (implementace / budoucí použití).
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

# R21a: záložky skutečně zobrazené v editoru Identifikace.
HAZARD_IDENTIFICATION_VISIBLE_TABS = (
    TAB_BASICS,
    TAB_PHOTOS,
    TAB_INVENTORY,
    TAB_RISK_ASSESSMENT,
)

DIALOG_WINDOW_TITLE = "Identifikace rizik"

INVENTORY_INTRO_TEXT = (
    "Evidujte výskyt katalogových zdrojů rizik na tomto pracovišti. "
    "Odborný obsah zdrojů se spravuje v Katalogu zdrojů rizik; zde jen "
    "zaznamenáváte, které zdroje se na pracovišti vyskytují."
)
INVENTORY_ADD_NEW_BUTTON = "Přidat nový"

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

# UX-RISK-3: výchozí seed číselníku (kód, název, popis, pořadí).
DEFAULT_HAZARD_SOURCE_CATEGORIES = (
    (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        "Stroje a technická zařízení",
        "Stroje, linky a technická zařízení na pracovišti.",
        1,
    ),
    (
        HAZARD_INVENTORY_CATEGORY_ACTIVITY,
        "Nářadí a pracovní prostředky",
        "Ruční nářadí, přípravky a pracovní prostředky.",
        2,
    ),
    (
        HAZARD_INVENTORY_CATEGORY_ENERGY,
        "Energie a fyzikální faktory",
        "Elektrická energie, tlak, teplo, záření a další fyzikální faktory.",
        3,
    ),
    (
        HAZARD_INVENTORY_CATEGORY_SUBSTANCE,
        "Látky, materiály a prach",
        "Chemické látky, materiály a prašné zdroje.",
        4,
    ),
    (
        HAZARD_INVENTORY_CATEGORY_STRUCTURE,
        "Prostory, konstrukce a povrchy",
        "Stavební konstrukce, podlahy, stropy a povrchy.",
        5,
    ),
    (
        HAZARD_INVENTORY_CATEGORY_TRANSPORT,
        "Vozidla a dopravní prostředky",
        "Vozidla, manipulační technika a dopravní prostředky.",
        6,
    ),
    (
        HAZARD_INVENTORY_CATEGORY_PERSON,
        "Biologické zdroje a živé organismy",
        "Biologické agens a živé organismy.",
        7,
    ),
    (
        HAZARD_INVENTORY_CATEGORY_ENVIRONMENT,
        "Přírodní a klimatické vlivy",
        "Přírodní podmínky a klimatické vlivy na pracovišti.",
        8,
    ),
    (
        HAZARD_INVENTORY_CATEGORY_OTHER,
        "Ostatní zdroje",
        "Ostatní zdroje rizik mimo předchozí kategorie.",
        9,
    ),
)

# Starší názvy – migrace přejmenuje pouze řádky se shodou (ne uživatelské přejmenování).
LEGACY_HAZARD_SOURCE_CATEGORY_NAMES = {
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

HAZARD_INVENTORY_CATEGORY_LABELS = {
    code: name for code, name, _description, _order in DEFAULT_HAZARD_SOURCE_CATEGORIES
}

READ_ONLY_IDENTIFICATION_STATUSES = (
    HAZARD_IDENTIFICATION_STATUS_COMPLETED,
    HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
)

INVENTORY_ITEM_DIALOG_TITLE = "Zdroj rizika na pracovišti"


def format_inventory_item_source_label(
    *,
    source_template_id: int | None,
    source_template_version: int | None,
) -> str:
    if source_template_id is None:
        return ""
    version = source_template_version if source_template_version is not None else "—"
    return f"Katalog zdrojů rizik (ID {source_template_id}, revize {version})"

INVENTORY_COL_ID = 0
INVENTORY_COL_NAME = 1
INVENTORY_COL_DESCRIPTION = 2
INVENTORY_COL_ACTIVE = 3
INVENTORY_COLUMN_COUNT = 4

INVENTORY_TABLE_HEADERS = ["ID", "Název", "Popis", "Aktivní"]

WORKPLACE_ANALYSIS_SELECT_ITEM = "Vyberte zdroj rizika na pracovišti."

WORKPLACE_ANALYSIS_READ_ONLY_MESSAGE = (
    "Zdroje rizik na pracovišti jsou u dokončené nebo archivované identifikace "
    "pouze pro čtení."
)


def is_identification_inventory_read_only(status: str) -> bool:
    return status in READ_ONLY_IDENTIFICATION_STATUSES


def can_save_inventory_item_to_library(status: str) -> bool:
    """Uložení zdroje do katalogu – povoleno kromě archivované identifikace."""
    return status != HAZARD_IDENTIFICATION_STATUS_ARCHIVED


PHOTOS_INTRO_TEXT = (
    "Fotodokumentace zachycuje skutečný stav pracoviště v době identifikace. "
    "Slouží jako podklad k evidenci výskytu zdrojů rizik na místě."
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
    "Nežádoucí události příslušné k evidovaným zdrojům rizik na pracovišti."
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
    "Zdroj rizika",
    "Aktivní",
]

# Tabulka událostí v záložce Zdroje rizik na pracovišti (bez sloupce Zdroj rizika).
ITEM_EVENT_COL_ID = 0
ITEM_EVENT_COL_NAME = 1
ITEM_EVENT_COL_ACTIVE = 2
ITEM_EVENT_COLUMN_COUNT = 3
ITEM_EVENT_TABLE_HEADERS = ["ID", "Nežádoucí událost", "Aktivní"]

ITEM_EVENTS_SELECT_ITEM = "Vyberte zdroj rizika na pracovišti."
ITEM_EVENTS_SELECT_EVENT = "Vyberte nežádoucí událost."
ITEM_EVENTS_SECTION_TITLE = "Nežádoucí události vybraného zdroje rizika"


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
    "Posouzení rizik převzatá z katalogových zdrojů evidovaných na tomto pracovišti. "
    "U každého posouzení je uvedena ohrožená skupina, nežádoucí událost a závažnost."
)

HAZARD_RISK_ASSESSMENT_DIALOG_TITLE = "Posouzení zdroje rizika"

RISK_ASSESSMENT_COL_ID = 0
RISK_ASSESSMENT_COL_EXPOSED_GROUP = 1
RISK_ASSESSMENT_COL_EVENT = 2
RISK_ASSESSMENT_COL_INVENTORY_ITEM = 3
RISK_ASSESSMENT_COL_SEVERITY = 4
RISK_ASSESSMENT_COL_STATUS = 5
RISK_ASSESSMENT_COL_COMPLETED_AT = 6
RISK_ASSESSMENT_COL_ACTIVE = 7
RISK_ASSESSMENT_COLUMN_COUNT = 8

RISK_ASSESSMENT_TABLE_HEADERS = [
    "ID",
    "Ohrožené skupiny",
    "Nežádoucí událost",
    "Zdroj rizika",
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


EXISTING_MEASURES_TITLE = "Zásady bezpečné práce"
HAZARD_EXISTING_MEASURE_DIALOG_TITLE = "Zásady bezpečné práce"
EXISTING_MEASURE_SELECT_ASSESSMENT = "Vyberte posouzení rizika."

EXISTING_MEASURE_COL_ID = 0
EXISTING_MEASURE_COL_DESCRIPTION = 1
EXISTING_MEASURE_COL_NOTE = 2
EXISTING_MEASURE_COL_ACTIVE = 3
EXISTING_MEASURE_COLUMN_COUNT = 4

EXISTING_MEASURE_TABLE_HEADERS = ["ID", "Opatření", "Poznámka", "Aktivní"]

REQUIRED_MEASURES_TITLE = "Navazující opatření"
HAZARD_REQUIRED_MEASURE_DIALOG_TITLE = "Navazující opatření"
REQUIRED_MEASURE_SELECT_ASSESSMENT = "Vyberte posouzení rizika."

REQUIRED_MEASURE_COL_ID = 0
REQUIRED_MEASURE_COL_TITLE = 1
REQUIRED_MEASURE_COL_DESCRIPTION = 2
REQUIRED_MEASURE_COL_ACTIVE = 3
REQUIRED_MEASURE_COLUMN_COUNT = 4

# Zpětná kompatibilita se starším názvem sloupce.
REQUIRED_MEASURE_COL_NOTE = REQUIRED_MEASURE_COL_DESCRIPTION

REQUIRED_MEASURE_TABLE_HEADERS = ["ID", "Název", "Popis", "Aktivní"]

HAZARD_IDENTIFICATION_UNSAVED_PROMPT = "Uložit změny před zavřením?"
HAZARD_IDENTIFICATION_UNSAVED_SAVE = "Uložit"
HAZARD_IDENTIFICATION_UNSAVED_DISCARD = "Neukládat"
HAZARD_IDENTIFICATION_UNSAVED_STAY = "Zrušit"
HAZARD_IDENTIFICATION_CANCEL_CONFIRM = "Zahodit všechny neuložené změny a zavřít editor?"
HAZARD_IDENTIFICATION_SAVE_SUCCESS = "Změny byly uloženy."

# --- Přezkoumání opatření (RISK-REVIEW-1) ---

RISK_MEASURE_REVIEW_TAB_TITLE = "Přezkoumání opatření"
RISK_MEASURE_REVIEW_DIALOG_TITLE = "Přezkoumání opatření"
RISK_MEASURE_REVIEW_CHECKLIST_TITLE = "Checklist přezkoumání"
RISK_MEASURE_REVIEW_CHECKLIST_PLACEHOLDER = (
    "Kontrolní body budou vytvořeny z navazujících opatření v další fázi."
)
RISK_MEASURE_REVIEW_CHECKLIST_EMPTY = (
    "Pro zvolený rozsah nebyla nalezena žádná aktivní navazující opatření."
)

RISK_MEASURE_REVIEW_STATUS_DRAFT = "draft"
RISK_MEASURE_REVIEW_STATUS_COMPLETED = "completed"
RISK_MEASURE_REVIEW_STATUS_ARCHIVED = "archived"

RISK_MEASURE_REVIEW_STATUSES = (
    RISK_MEASURE_REVIEW_STATUS_DRAFT,
    RISK_MEASURE_REVIEW_STATUS_COMPLETED,
)

RISK_MEASURE_REVIEW_STATUS_LABELS = {
    RISK_MEASURE_REVIEW_STATUS_DRAFT: "Rozpracováno",
    RISK_MEASURE_REVIEW_STATUS_COMPLETED: "Dokončeno",
    RISK_MEASURE_REVIEW_STATUS_ARCHIVED: "Archivováno",
}

# RISK-UX-7a: základní filtry seznamů
RISK_LIST_FILTER_ACTIVE = "Aktivní"
RISK_LIST_FILTER_INACTIVE = "Neaktivní"
RISK_LIST_FILTER_ALL = "Vše"
RISK_IDENTIFICATION_DEFAULT_ACTIVE_FILTER = RISK_LIST_FILTER_ACTIVE

RISK_MEASURE_REVIEW_FILTER_ALL = "Vše"
RISK_MEASURE_REVIEW_DEFAULT_STATUS_FILTER = RISK_MEASURE_REVIEW_STATUS_DRAFT

RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED = "not_checked"
RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT = "compliant"
RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT = "non_compliant"

RISK_MEASURE_REVIEW_ITEM_RESULTS = (
    RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
    RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
)

RISK_MEASURE_REVIEW_ITEM_RESULT_LABELS = {
    RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED: "Nehodnoceno",
    RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT: "Vyhovuje",
    RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT: "Nevyhovuje",
}

# RISK-REVIEW-5: způsob řešení nevyhovujícího kontrolního bodu
RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED = ""
RISK_MEASURE_REVIEW_ITEM_RESOLUTION_TASK = "task"
RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION = "measure_revision"

RISK_MEASURE_REVIEW_ITEM_RESOLUTIONS = (
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED,
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_TASK,
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION,
)

RISK_MEASURE_REVIEW_ITEM_RESOLUTION_LABELS = {
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED: "Nezpracováno",
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_TASK: "Založen úkol",
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION: "Revize opatření",
}

# RISK-REVIEW-4 – checklist provedení přezkoumání
RISK_MEASURE_REVIEW_ITEM_COL_ID = 0
RISK_MEASURE_REVIEW_ITEM_COL_MEASURE = 1
RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT = 2
RISK_MEASURE_REVIEW_ITEM_COL_NON_COMPLIANT = 3
RISK_MEASURE_REVIEW_ITEM_COL_PHOTO = 4
RISK_MEASURE_REVIEW_ITEM_COL_NOTE = 5
RISK_MEASURE_REVIEW_ITEM_COLUMN_COUNT = 6

RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS = [
    "ID",
    "Navazující opatření",
    "Vyhovuje",
    "Nevyhovuje",
    "Foto",
    "Poznámka",
]

# Zpětná kompatibilita se staršími názvy sloupců.
RISK_MEASURE_REVIEW_ITEM_COL_RESULT_TEXT = RISK_MEASURE_REVIEW_ITEM_COL_NOTE
RISK_MEASURE_REVIEW_ITEM_COL_NOTE_NUMBER = RISK_MEASURE_REVIEW_ITEM_COL_NOTE

RISK_MEASURE_REVIEW_NOTES_TITLE = "Poznámky"
RISK_MEASURE_REVIEW_NOTES_LINE_COUNT = 3

RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE = "Provést přezkoumání"
RISK_MEASURE_REVIEW_PRINT_BUTTON = "Vytisknout checklist"
RISK_MEASURE_REVIEW_PRINT_DIALOG_TITLE = "Checklist přezkoumání opatření"
RISK_MEASURE_REVIEW_PRINT_STUB_MESSAGE = (
    "Tisk checklistu bude doplněn v další fázi."
)
RISK_MEASURE_REVIEW_PRINT_EMPTY = "Checklist neobsahuje žádné kontrolní body."

ENTITY_RISK_MEASURE_REVIEW_ITEM = "risk_measure_review_item"
RISK_MEASURE_REVIEW_ITEM_PHOTOS_TITLE = "Fotografie kontrolního bodu"


# --- Úkoly přezkoumání (RISK-REVIEW-3a) ---

ENTITY_RISK_MEASURE_REVIEW = "risk_measure_review"
RISK_MEASURE_REVIEW_TASKS_TITLE = "Úkoly"
RISK_MEASURE_REVIEW_NON_COMPLIANT_EMPTY = (
    "Žádné nevyhovující kontrolní body. Označte bod jako „Nevyhovuje“ v checklistu."
)
RISK_MEASURE_REVIEW_RESOLUTION_REQUIRED = (
    "Před dokončením přezkoumání musí mít každý nevyhovující kontrolní bod "
    "zvolený způsob řešení (úkol nebo revize opatření)."
)
RISK_MEASURE_REVIEW_CREATE_TASK_LABEL = "Založit úkol"
RISK_MEASURE_REVIEW_OPEN_REVISION_LABEL = "Otevřít revizi opatření"
RISK_MEASURE_REVIEW_RESOLUTION_TASK_OPTION = "Založit úkol"
RISK_MEASURE_REVIEW_RESOLUTION_REVISION_OPTION = "Provést revizi opatření proti riziku"

RISK_MEASURE_REVIEW_COL_ID = 0
RISK_MEASURE_REVIEW_COL_NUMBER = 1
RISK_MEASURE_REVIEW_COL_DATE = 2
RISK_MEASURE_REVIEW_COL_OPERATION = 3
RISK_MEASURE_REVIEW_COL_WORKPLACE = 4
RISK_MEASURE_REVIEW_COL_WORKPLACE_PART = 5
RISK_MEASURE_REVIEW_COL_REVIEWER = 6
RISK_MEASURE_REVIEW_COL_STATUS = 7
RISK_MEASURE_REVIEW_COLUMN_COUNT = 8

RISK_MEASURE_REVIEW_TABLE_HEADERS = [
    "ID",
    "Číslo",
    "Datum",
    "Provoz",
    "Pracoviště",
    "Část pracoviště",
    "Kontrolující",
    "Stav",
]


def format_risk_measure_review_status_label(status: str) -> str:
    return RISK_MEASURE_REVIEW_STATUS_LABELS.get(status, status or "—")


def format_inventory_item_display_name(
    name: str,
    *,
    event_count: int = 0,
) -> str:
    if not event_count:
        return name
    suffix = "událost" if event_count == 1 else "událostí"
    return f"{name} — {event_count} {suffix}"
