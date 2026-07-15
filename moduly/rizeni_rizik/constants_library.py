"""Konstanty katalogu zdrojů rizik (R17a+, Master model R17d)."""

HAZARD_LIBRARY_SCOPE_ALL = "all_operations"
HAZARD_LIBRARY_SCOPE_SELECTED = "selected_operations"
HAZARD_LIBRARY_SCOPE_MANUAL = "manual"

DEFAULT_HAZARD_LIBRARY_SCOPE = HAZARD_LIBRARY_SCOPE_MANUAL

HAZARD_LIBRARY_SCOPES = (
    HAZARD_LIBRARY_SCOPE_ALL,
    HAZARD_LIBRARY_SCOPE_SELECTED,
    HAZARD_LIBRARY_SCOPE_MANUAL,
)

HAZARD_LIBRARY_SCOPE_LABELS = {
    HAZARD_LIBRARY_SCOPE_ALL: "Všechny provozy",
    HAZARD_LIBRARY_SCOPE_SELECTED: "Vybrané provozy",
    HAZARD_LIBRARY_SCOPE_MANUAL: "Bez předem určeného rozsahu",
}

HAZARD_LIBRARY_PAGE_TITLE = "Katalog zdrojů rizik"
HAZARD_LIBRARY_DIALOG_TITLE = "Zdroj rizika"
HAZARD_LIBRARY_NEW_BUTTON = "Nový zdroj rizika"

HAZARD_LIBRARY_TAB_BASICS = "Základní údaje"
HAZARD_LIBRARY_TAB_CONTENT = "Odborný obsah"
HAZARD_LIBRARY_TAB_AI_PEER_REVIEW = "Oponentní posouzení AI"
HAZARD_LIBRARY_TAB_USAGE = "Použití zdroje"
HAZARD_LIBRARY_TAB_HISTORY = "Historie změn"

HAZARD_LIBRARY_PLACEHOLDER_TEXT = "Obsah bude doplněn v další fázi."

HAZARD_LIBRARY_CONTENT_INTRO_TEXT = (
    "Nežádoucí události, posouzení rizik a opatření zdroje. "
    "Obsah se zadává ručně a slouží jako opakovaně použitelný odborný podklad."
)
HAZARD_LIBRARY_CONTENT_READ_ONLY_MESSAGE = (
    "Neaktivní zdroj rizika lze zobrazit pouze pro čtení."
)
HAZARD_LIBRARY_EVENT_DIALOG_TITLE = "Nežádoucí událost zdroje rizika"
HAZARD_LIBRARY_ASSESSMENTS_DIALOG_TITLE = "Posouzení a opatření zdroje rizika"
HAZARD_LIBRARY_ASSESSMENT_DIALOG_TITLE = "Posouzení zdroje rizika"
HAZARD_LIBRARY_EXISTING_MEASURE_DIALOG_TITLE = "Existující opatření zdroje rizika"
HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE = "Potřebné opatření zdroje rizika"

HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ID = 0
HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME = 1
HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE = 2
HAZARD_LIBRARY_TEMPLATE_EVENT_COLUMN_COUNT = 3
HAZARD_LIBRARY_TEMPLATE_EVENT_TABLE_HEADERS = [
    "ID",
    "Název",
    "Aktivní",
]

HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ID = 0
HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_GROUP = 1
HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_CONSEQUENCE = 2
HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_SEVERITY = 3
HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ACTIVE = 4
HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COLUMN_COUNT = 5
HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_TABLE_HEADERS = [
    "ID",
    "Ohrožená skupina",
    "Možný následek",
    "Závažnost",
    "Aktivní",
]

HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ID = 0
HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_DESCRIPTION = 1
HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_NOTE = 2
HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE = 3
HAZARD_LIBRARY_TEMPLATE_MEASURE_COLUMN_COUNT = 4
HAZARD_LIBRARY_TEMPLATE_MEASURE_TABLE_HEADERS = [
    "ID",
    "Popis",
    "Poznámka",
    "Aktivní",
]

HAZARD_LIBRARY_TEMPLATE_EXISTING_MEASURES_TITLE = "Existující opatření"
HAZARD_LIBRARY_TEMPLATE_REQUIRED_MEASURES_TITLE = "Potřebná další opatření"
HAZARD_LIBRARY_TEMPLATE_SELECT_ASSESSMENT = "Vyberte posouzení pro zobrazení opatření."
HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT = "Vyberte nežádoucí událost."
HAZARD_LIBRARY_TEMPLATE_EVENTS_SECTION_TITLE = "Nežádoucí události"

HAZARD_LIBRARY_SAVE_FROM_INVENTORY_DIALOG_TITLE = "Uložit do katalogu zdrojů rizik"
HAZARD_LIBRARY_SAVE_FROM_INVENTORY_SUCCESS_TITLE = "Zdroj rizika uložen do katalogu"
HAZARD_LIBRARY_SAVE_TO_LIBRARY_BUTTON = "Uložit do katalogu zdrojů rizik…"
HAZARD_LIBRARY_OPEN_IN_LIBRARY_BUTTON = "Otevřít v katalogu zdrojů rizik"
HAZARD_LIBRARY_SAVE_INACTIVE_ITEM_MESSAGE = (
    "Do katalogu lze uložit pouze aktivní položku analýzy pracoviště."
)
HAZARD_LIBRARY_SAVE_ARCHIVED_MESSAGE = (
    "U archivované identifikace nelze ukládat položky do katalogu zdrojů rizik."
)

HAZARD_LIBRARY_APPLY_TO_INVENTORY_BUTTON = "Převzít z Katalogu"
HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE = "Převzít z Katalogu"
HAZARD_LIBRARY_RECOMMENDED_SOURCES_TITLE = "Doporučené zdroje"
HAZARD_LIBRARY_OTHER_SOURCES_TITLE = "Ostatní zdroje"
HAZARD_LIBRARY_APPLY_TO_INVENTORY_SUCCESS_TITLE = "Zdroj převzat z katalogu"
HAZARD_LIBRARY_APPLY_ARCHIVED_MESSAGE = (
    "U archivované identifikace nelze převzít zdroj z katalogu."
)

CATALOG_COMPARE_KIND_ADDED = "+"
CATALOG_COMPARE_KIND_REMOVED = "-"
CATALOG_COMPARE_KIND_CHANGED = "~"

CATALOG_COMPARE_WITH_MASTER_BUTTON = "Porovnat s Masterem…"
CATALOG_COMPARE_WITH_MASTER_DIALOG_TITLE = "Porovnání s Masterem"
CATALOG_COMPARE_WITH_MASTER_INTRO = (
    "Master\n\n↓\n\nLokální změny\n\n"
    "Legenda: + nová položka, − odebraná položka, ~ změněný text"
)
CATALOG_COMPARE_WITH_MASTER_NO_DIFFERENCES = (
    "Lokální instance odpovídá Master zdroji (bez zaznamenaných odchylek)."
)
CATALOG_COMPARE_WITH_MASTER_VERSION_NOTE = (
    "Poznámka: Master je v revizi {master_version}, instance byla převzata v revizi {source_version}."
)
CATALOG_COMPARE_WITH_MASTER_SELECT_ITEM = (
    "Vyberte zdroj analýzy převzatý z katalogu."
)
CATALOG_COMPARE_WITH_MASTER_NOT_CATALOG_ITEM = (
    "Porovnání s Masterem je dostupné pouze u zdroje převzatého z katalogu."
)

CATALOG_UPDATE_OFFER_DIALOG_TITLE = "Aktualizace z Master"
CATALOG_UPDATE_OFFER_INTRO = "V katalogu je dostupná novější revize tohoto zdroje."
CATALOG_UPDATE_OFFER_CHOICE_UPDATE = "Aktualizovat"
CATALOG_UPDATE_OFFER_CHOICE_SHOW_DIFF = "Zobrazit rozdíly"
CATALOG_UPDATE_OFFER_CHOICE_KEEP = "Ponechat"
CATALOG_UPDATE_SUCCESS_TITLE = "Aktualizace z Master"
CATALOG_UPDATE_SUCCESS_TEXT = (
    "Lokální instance byla aktualizována z Master zdroje. "
    "Revize instance: {previous_version} → {new_version}."
)

HAZARD_LIBRARY_COL_ID = 0
HAZARD_LIBRARY_COL_NAME = 1
HAZARD_LIBRARY_COL_CATEGORY = 2
HAZARD_LIBRARY_COL_SCOPE = 3
HAZARD_LIBRARY_COL_VERSION = 4
HAZARD_LIBRARY_COL_OPERATION_COUNT = 5
HAZARD_LIBRARY_COL_ACTIVE = 6
HAZARD_LIBRARY_COLUMN_COUNT = 7

HAZARD_LIBRARY_TABLE_HEADERS = [
    "ID",
    "Název",
    "Kategorie",
    "Rozsah použití",
    "Revize",
    "Počet provozů",
    "Aktivní",
]

HAZARD_LIBRARY_REVISION_FORM_LABEL = "Revize:"
HAZARD_LIBRARY_REVISION_READ_ONLY_TOOLTIP = (
    "Číslo revize odborného obsahu. Zvyšuje se automaticky při uložení změn obsahu."
)

HAZARD_LIBRARY_REVISION_REASON_MANUAL = "manual_edit"
HAZARD_LIBRARY_REVISION_REASON_FROM_IDENTIFICATION = "from_identification"
HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS = "ai_proposals"
HAZARD_LIBRARY_REVISION_REASON_MASTER_UPDATE = "master_update"

HAZARD_LIBRARY_REVISION_REASON_LABELS = {
    HAZARD_LIBRARY_REVISION_REASON_MANUAL: "Ruční úprava odborného obsahu",
    HAZARD_LIBRARY_REVISION_REASON_FROM_IDENTIFICATION: "Převzato z identifikace pracoviště",
    HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS: "Převzaty návrhy AI",
    HAZARD_LIBRARY_REVISION_REASON_MASTER_UPDATE: "Aktualizace z Master",
}

HAZARD_LIBRARY_REVISION_HISTORY_COL_NUMBER = 0
HAZARD_LIBRARY_REVISION_HISTORY_COL_CREATED_AT = 1
HAZARD_LIBRARY_REVISION_HISTORY_COL_REASON = 2
HAZARD_LIBRARY_REVISION_HISTORY_COLUMN_COUNT = 3
HAZARD_LIBRARY_REVISION_HISTORY_HEADERS = [
    "Revize",
    "Datum a čas",
    "Důvod změny",
]
HAZARD_LIBRARY_REVISION_HISTORY_EMPTY = (
    "Zatím nejsou zaznamenány žádné revize odborného obsahu."
)

CATALOG_UPDATE_OFFER_REVISION_INSTANCE = "Revize instance: {revision}"
CATALOG_UPDATE_OFFER_REVISION_MASTER = "Revize Master: {revision}"

CATALOG_AI_PROPOSAL_INCORPORATE_BUTTON = "Zapracovat"
CATALOG_AI_PROPOSAL_REJECT_BUTTON = "Zamítnout"
CATALOG_AI_PROPOSAL_EDIT_BUTTON = "Upravit…"
CATALOG_AI_PROPOSAL_INCORPORATE_SELECTED_BUTTON = "Zapracovat vybrané"
CATALOG_AI_PROPOSAL_REJECT_SELECTED_BUTTON = "Zamítnout vybrané"
CATALOG_AI_PROPOSAL_QUEUE_LABEL = "Návrhy ke zpracování (čekají na odborné posouzení):"
CATALOG_AI_PROPOSAL_INCORPORATE_SUCCESS = (
    "Do MASTER obsahu bylo zapracováno {count} návrhů. Revize zdroje: {revision}."
)
CATALOG_AI_PROPOSAL_INCORPORATE_SUMMARY = (
    "Zapracování dokončeno.\n\n"
    "Nově zapracováno:\n{newly_incorporated}\n\n"
    "Použito existujících položek:\n{used_existing}\n\n"
    "Přeskočeno:\n{skipped}\n\n"
    "Zamítnuto:\n{rejected}\n\n"
    "Nová revize:\n{revision}"
)
CATALOG_AI_PROPOSAL_REJECT_SUCCESS = "Zamítnuto návrhů: {count}."
CATALOG_AI_PROPOSAL_DUPLICATE_DIALOG_TITLE = "Duplicitní návrh"
CATALOG_AI_PROPOSAL_DUPLICATE_INTRO = (
    "Návrh „{proposal_name}“ je v konfliktu s existující položkou „{existing_label}“."
)
CATALOG_AI_PROPOSAL_DUPLICATE_SIMILAR_INTRO = (
    "Návrh „{proposal_name}“ je podobný existující položce „{existing_label}“.\n"
    "Vyberte, jak s návrhem naložit."
)
CATALOG_AI_PROPOSAL_DUPLICATE_SKIP = "Přeskočit"
CATALOG_AI_PROPOSAL_DUPLICATE_MERGE = "Sloučit"
CATALOG_AI_PROPOSAL_DUPLICATE_EDIT = "Upravit"
CATALOG_AI_PROPOSAL_DUPLICATE_CANCEL = "Zrušit zapracování"
CATALOG_AI_PROPOSAL_EDIT_DIALOG_TITLE = "Úprava návrhu AI"
CATALOG_AI_PROPOSAL_LEGAL_EDIT_INFO = (
    "Právní vazbu lze upravit pouze jako text návrhu. Do MASTER obsahu se nezapisuje."
)

DEFAULT_HAZARD_LIBRARY_VERSION = 1
