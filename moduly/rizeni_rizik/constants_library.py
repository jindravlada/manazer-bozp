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
HAZARD_LIBRARY_UNSAVED_PROMPT = "Máte neuložené změny. Co chcete udělat?"
HAZARD_LIBRARY_UNSAVED_SAVE = "Uložit"
HAZARD_LIBRARY_UNSAVED_DISCARD = "Zahodit"
HAZARD_LIBRARY_UNSAVED_STAY = "Zůstat"
HAZARD_LIBRARY_CANCEL_CONFIRM = "Zahodit všechny neuložené změny a zavřít editor?"
HAZARD_LIBRARY_SAVE_SUCCESS = "Změny byly uloženy."
HAZARD_LIBRARY_DUPLICATE_NAME_TITLE = "Zdroj rizika již existuje"
HAZARD_LIBRARY_DUPLICATE_NAME_TEXT = (
    "Aktivní zdroj rizika se stejným názvem již v katalogu existuje.\n\n"
    "Chcete otevřít existující zdroj, nebo pokračovat vytvořením nového?"
)
HAZARD_LIBRARY_DUPLICATE_OPEN_EXISTING = "Otevřít existující"
HAZARD_LIBRARY_DUPLICATE_CREATE_NEW = "Vytvořit nový"
HAZARD_LIBRARY_DUPLICATE_CANCEL = "Zrušit"

HAZARD_LIBRARY_TAB_BASICS = "Základní údaje"
HAZARD_LIBRARY_TAB_CONTENT = "Odborný obsah"
HAZARD_LIBRARY_TAB_AI_PEER_REVIEW = "Oponentní posouzení AI"
HAZARD_LIBRARY_TAB_USAGE = "Použití zdroje"
HAZARD_LIBRARY_TAB_HISTORY = "Historie změn"

HAZARD_LIBRARY_PLACEHOLDER_TEXT = "Obsah bude doplněn v další fázi."

HAZARD_LIBRARY_CONTENT_INTRO_TEXT = (
    "Nežádoucí události, posouzení rizik, opatření a právní vazby zdroje. "
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
HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE = "Právní vazba zdroje rizika"

HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ID = 0
HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_REQUIREMENT = 1
HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_DOCUMENT = 1
HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_NOTE = 2
HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ACTIVE = 3
HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COLUMN_COUNT = 4
HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_TABLE_HEADERS = [
    "ID",
    "Právní předpis",
    "Poznámka",
    "Aktivní",
]
HAZARD_LIBRARY_TEMPLATE_LEGAL_LINKS_SECTION_TITLE = "Právní vazby"
HAZARD_LIBRARY_TEMPLATE_SELECT_LEGAL_LINK = "Vyberte právní vazbu."
HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_REQUIREMENT_REQUIRED = (
    "Vyberte právní požadavek z registru řídicích procesů."
)
HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_DOCUMENT_REQUIRED = (
    "Vyberte právní předpis."
)

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
HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_SEVERITY = 2
HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ACTIVE = 3
HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COLUMN_COUNT = 4
HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_TABLE_HEADERS = [
    "ID",
    "Ohrožené skupiny",
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
HAZARD_LIBRARY_CATALOG_SOURCES_TITLE = "Zdroje rizika z katalogu"
HAZARD_LIBRARY_APPLY_CATEGORY_FILTER_LABEL = "Kategorie:"
HAZARD_LIBRARY_APPLY_ALL_CATEGORIES = "Všechny kategorie"
HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE = "Zobrazeno: {shown} z {total} zdrojů"
HAZARD_LIBRARY_RECOMMENDED_SOURCES_TITLE = "Doporučené zdroje"  # legacy R18a
HAZARD_LIBRARY_OTHER_SOURCES_TITLE = "Ostatní zdroje"  # legacy R18a
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
HAZARD_LIBRARY_COL_VERSION = 3
HAZARD_LIBRARY_COL_ACTIVE = 4
HAZARD_LIBRARY_COLUMN_COUNT = 5

HAZARD_LIBRARY_TABLE_HEADERS = [
    "ID",
    "Název",
    "Kategorie",
    "Revize",
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
CATALOG_AI_PACKAGE_QUEUE_LABEL = "Návrhové balíky ke zpracování:"
CATALOG_AI_PACKAGE_DETAIL_LABEL = "Detail balíku:"
CATALOG_AI_PACKAGE_EDIT_BUTTON = "Upravit balík…"
CATALOG_AI_PACKAGE_INCORPORATE_BUTTON = "Zapracovat balík"
CATALOG_AI_PACKAGE_REJECT_BUTTON = "Zamítnout balík"
CATALOG_AI_PACKAGE_EDIT_DIALOG_TITLE = "Úprava návrhového balíku"
CATALOG_AI_PACKAGE_EDIT_SAVE_BUTTON = "Uložit změny"
CATALOG_AI_PACKAGE_SUMMARY_TITLE = "Souhrn balíku"
CATALOG_AI_PACKAGE_INCORPORATE_SUCCESS = (
    "Balík byl zapracován do MASTER obsahu. Revize zdroje: {revision}."
)
CATALOG_AI_PACKAGE_INCORPORATE_PENDING_SAVE = (
    "Balík byl zapracován do pracovní kopie. "
    "Stav „Zapracováno“ a nová revize se uloží až po stisku Uložit."
)
CATALOG_AI_PACKAGE_REJECT_SUCCESS = "Balík byl zamítnut."
CATALOG_AI_PACKAGE_SELECT_ONE = "Vyberte právě jeden návrhový balík."
CATALOG_AI_PACKAGE_EMPTY_DETAIL = "Vyberte balík v seznamu pro zobrazení detailu."
CATALOG_AI_PROPOSAL_INCORPORATE_SUCCESS = (
    "Do MASTER obsahu bylo zapracováno {count} návrhů. Revize zdroje: {revision}."
)
CATALOG_AI_PROPOSAL_INCORPORATE_SUMMARY = (
    "Zapracování dokončeno.\n\n"
    "Zapracováno:\n{newly_incorporated}\n\n"
    "Použito existujících:\n{used_existing}\n\n"
    "Vyžaduje ruční rozhodnutí:\n{requires_manual_decision}\n\n"
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
    "Právní vazba se zapracuje jako odkaz na existující právní předpis v registru."
)
CATALOG_AI_PROPOSAL_REQUIREMENT_CHOICE_DIALOG_TITLE = "Výběr právního předpisu"
CATALOG_AI_PROPOSAL_REQUIREMENT_CHOICE_INTRO = (
    "Návrh „{proposal_name}“ odpovídá více právním předpisům.\n"
    "Vyberte správný předpis nebo návrh přeskočte."
)
CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_DIALOG_TITLE = "Výběr posouzení pro opatření"
CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_INTRO = (
    "AI neurčila, ke kterému posouzení rizika opatření patří."
)
CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_EVENT_COLUMN = "Událost"
CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_GROUP_COLUMN = "Ohrožená skupina"
CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_USE_BUTTON = "Použít vybrané posouzení"
CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_DIALOG_TITLE = "Duplicitní posouzení pro skupinu"
CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_INTRO = (
    "Ohrožená skupina „{group_name}“ je obsažena ve více aktivních posouzeních "
    "stejné události.\n"
    "Vyberte cílové posouzení, do kterého se má AI návrh zapracovat."
)
CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_COLUMN_SEVERITY = "Závažnost"
CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_COLUMN_CONCLUSION = "Závěr"
CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_USE_BUTTON = "Použít vybrané posouzení"
CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_BUTTON = "Vytvořit nové posouzení"
CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_DIALOG_TITLE = "Chybí vhodné posouzení"
CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_INTRO = (
    "AI neurčila, ke kterému posouzení rizika opatření „{proposal_name}“ patří.\n"
    "Ve zdroji rizika zatím není vhodné posouzení, ke kterému by šlo opatření zařadit."
)
CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_EVENT_DIALOG_TITLE = "Výběr události pro nové posouzení"
CATALOG_AI_PROPOSAL_REQUIREMENT_NOT_FOUND_INFO = (
    "Právní předpis pro návrh „{proposal_name}“ nebyl v registru nalezen. "
    "Návrh zůstane ve frontě ke zpracování."
)

CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_OFFER_TITLE = "Ruční dokončení zapracování"
CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_OFFER_TEXT = (
    "Po automatickém zapracování zbývá {count} návrhů vyžadujících ruční rozhodnutí.\n\n"
    "Průvodce vás provede dokončením jednotlivých návrhů."
)
CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_OPEN_BUTTON = "Otevřít první problémový návrh"
CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_LATER_BUTTON = "Později"
CATALOG_AI_PROPOSAL_MANUAL_REQUIREMENT_INTRO = (
    "Právní předpis pro návrh „{proposal_name}“ nebyl nalezen automaticky.\n"
    "Vyberte správný předpis z registru."
)
CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_DEFERRED = (
    "Zapracování bylo částečně dokončeno. "
    "Návrhy vyžadující ruční zásah zůstávají ve frontě ke zpracování."
)
CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_PROGRESS = (
    "Návrh {current} z {total}: „{proposal_name}“"
)

CATALOG_INCORPORATE_ERROR_SELECT_PROPOSALS = "Vyberte alespoň jeden návrh ke zapracování."
CATALOG_INCORPORATE_ERROR_SOURCE_MISSING = "Zdroj rizika neexistuje nebo není dostupný."
CATALOG_INCORPORATE_ERROR_SOURCE_INACTIVE = (
    "Návrhy lze zapracovat pouze do aktivního zdroje rizika."
)
CATALOG_INCORPORATE_ERROR_REVIEW_MISSING = "Vybraná konzultace AI neexistuje."
CATALOG_INCORPORATE_ERROR_REVIEW_MISMATCH = (
    "Vybraná konzultace nepatří k tomuto zdroji rizika."
)
CATALOG_INCORPORATE_ERROR_NO_PENDING = (
    "Vybrané návrhy nejsou ve stavu čekajícím na odborné posouzení."
)
CATALOG_INCORPORATE_ERROR_UNKNOWN_AREA = (
    "Návrh „{name}“ nelze zařadit do známé oblasti odborného obsahu."
)
CATALOG_INCORPORATE_ERROR_EVENT_PARENT = (
    "Návrh události „{name}“ nelze zařadit ke zdroji rizika."
)
CATALOG_INCORPORATE_ERROR_ASSESSMENT_PARENT = (
    "Návrh posouzení „{name}“ nelze zařadit k nežádoucí události."
)
CATALOG_INCORPORATE_ERROR_ASSESSMENT_GROUP = (
    "Návrh posouzení „{name}“ nemá určenou ohroženou skupinu."
)
CATALOG_INCORPORATE_ERROR_MEASURE_PARENT = (
    "Návrh opatření „{name}“ nelze zařadit k posouzení rizika."
)
CATALOG_INCORPORATE_ERROR_EXPOSED_GROUP = (
    "Návrh ohrožené skupiny nelze přímo zapsat do odborného obsahu zdroje."
)
CATALOG_INCORPORATE_ERROR_GENERIC = "Návrh „{name}“ nelze zapracovat."

DEFAULT_HAZARD_LIBRARY_VERSION = 1
