"""Konstanty modulu Koordinace BOZP."""

MODULE_KEY = "koordinace_bozp"
MODULE_NAME = "Koordinace BOZP"
MODULE_DESCRIPTION = (
    "Evidence koordinačních schůzek BOZP podle § 101 odst. 3 zákoníku práce."
)

DIALOG_WINDOW_TITLE = "Koordinace BOZP"

BOZP_COORDINATION_STATUS_DRAFT = "draft"
BOZP_COORDINATION_STATUS_READY = "ready"
BOZP_COORDINATION_STATUS_ISSUED = "issued"
BOZP_COORDINATION_STATUS_COMPLETED = "completed"
BOZP_COORDINATION_STATUS_ARCHIVED = "archived"

BOZP_COORDINATION_STATUSES = (
    BOZP_COORDINATION_STATUS_DRAFT,
    BOZP_COORDINATION_STATUS_READY,
    BOZP_COORDINATION_STATUS_ISSUED,
    BOZP_COORDINATION_STATUS_COMPLETED,
    BOZP_COORDINATION_STATUS_ARCHIVED,
)

DEFAULT_BOZP_COORDINATION_STATUS = BOZP_COORDINATION_STATUS_DRAFT

BOZP_COORDINATION_STATUS_LABELS = {
    BOZP_COORDINATION_STATUS_DRAFT: "Rozpracováno",
    BOZP_COORDINATION_STATUS_READY: "Připraveno k vydání",
    BOZP_COORDINATION_STATUS_ISSUED: "Vydáno",
    BOZP_COORDINATION_STATUS_COMPLETED: "Ukončeno",
    BOZP_COORDINATION_STATUS_ARCHIVED: "Archivováno",
}

# Barvy stavu (UX-COORD-6b) – v souladu s platností / PBP.
BOZP_COORDINATION_STATUS_COLORS = {
    BOZP_COORDINATION_STATUS_DRAFT: "#ef6c00",
    BOZP_COORDINATION_STATUS_READY: "#1565c0",
    BOZP_COORDINATION_STATUS_ISSUED: "#2e7d32",
    BOZP_COORDINATION_STATUS_COMPLETED: "#546e7a",
    BOZP_COORDINATION_STATUS_ARCHIVED: "#9e9e9e",
}

STATUS_FILTER_ALL = "all"
STATUS_FILTER_DRAFT = BOZP_COORDINATION_STATUS_DRAFT
STATUS_FILTER_READY = BOZP_COORDINATION_STATUS_READY
STATUS_FILTER_ISSUED = BOZP_COORDINATION_STATUS_ISSUED
STATUS_FILTER_COMPLETED = BOZP_COORDINATION_STATUS_COMPLETED
STATUS_FILTER_ARCHIVED = BOZP_COORDINATION_STATUS_ARCHIVED

STATUS_FILTERS = (
    STATUS_FILTER_ALL,
    STATUS_FILTER_DRAFT,
    STATUS_FILTER_READY,
    STATUS_FILTER_ISSUED,
    STATUS_FILTER_COMPLETED,
    STATUS_FILTER_ARCHIVED,
)

STATUS_FILTER_LABELS = {
    STATUS_FILTER_ALL: "Všechny",
    STATUS_FILTER_DRAFT: "Rozpracováno",
    STATUS_FILTER_READY: "Připraveno k vydání",
    STATUS_FILTER_ISSUED: "Vydáno",
    STATUS_FILTER_COMPLETED: "Ukončeno",
    STATUS_FILTER_ARCHIVED: "Archivováno",
}

# Označení verze v náhledu / ODT (UX-COORD-6b).
PROTOCOL_VERSION_MARK_DRAFT = "PRACOVNÍ VERZE"
PROTOCOL_VERSION_MARK_READY = "VERZE PŘIPRAVENÁ K VYDÁNÍ"

# Potvrzení akcí v UI (před validací builderem).
LIFECYCLE_ACTION_CONFIRM_MESSAGES = {
    "prepare": "Připravit koordinaci k vydání?",
    "issue": (
        "Vydáním označíte koordinační protokol jako vydaný.\n"
        "Dokument bude možné dále upravovat pouze po návratu "
        "do rozpracovaného stavu."
    ),
    "complete": "Ukončit koordinaci?",
    "archive": (
        "Archivovaná koordinace nebude určena k běžným úpravám.\n"
        "Opravdu archivovat?"
    ),
    "return_to_draft": "Vrátit koordinaci k dopracování?",
    "reopen": "Znovu otevřít koordinaci do stavu Rozpracováno?",
    "restore": "Obnovit archivovanou koordinaci do stavu Rozpracováno?",
}

READY_EDIT_REVERT_MESSAGE = (
    "Koordinace je připravena k vydání. "
    "Pokračováním bude vrácena do stavu Rozpracováno."
)

# Mapování starých / neznámých hodnot status → kanonický stav (UX-COORD-6a).
BOZP_COORDINATION_STATUS_LEGACY_MAP = {
    "draft": BOZP_COORDINATION_STATUS_DRAFT,
    "in_progress": BOZP_COORDINATION_STATUS_DRAFT,
    "ready": BOZP_COORDINATION_STATUS_READY,
    "prepared": BOZP_COORDINATION_STATUS_READY,
    "active": BOZP_COORDINATION_STATUS_READY,
    "issued": BOZP_COORDINATION_STATUS_ISSUED,
    "published": BOZP_COORDINATION_STATUS_ISSUED,
    "completed": BOZP_COORDINATION_STATUS_COMPLETED,
    "done": BOZP_COORDINATION_STATUS_COMPLETED,
    "archived": BOZP_COORDINATION_STATUS_ARCHIVED,
}

# Povolené přechody: from → frozenset(to)
BOZP_COORDINATION_STATUS_TRANSITIONS = {
    BOZP_COORDINATION_STATUS_DRAFT: frozenset(
        {
            BOZP_COORDINATION_STATUS_READY,
            BOZP_COORDINATION_STATUS_ARCHIVED,
        }
    ),
    BOZP_COORDINATION_STATUS_READY: frozenset(
        {
            BOZP_COORDINATION_STATUS_DRAFT,
            BOZP_COORDINATION_STATUS_ISSUED,
            BOZP_COORDINATION_STATUS_ARCHIVED,
        }
    ),
    BOZP_COORDINATION_STATUS_ISSUED: frozenset(
        {
            BOZP_COORDINATION_STATUS_COMPLETED,
            BOZP_COORDINATION_STATUS_DRAFT,
            BOZP_COORDINATION_STATUS_ARCHIVED,
        }
    ),
    BOZP_COORDINATION_STATUS_COMPLETED: frozenset(
        {
            BOZP_COORDINATION_STATUS_DRAFT,
            BOZP_COORDINATION_STATUS_ARCHIVED,
        }
    ),
    BOZP_COORDINATION_STATUS_ARCHIVED: frozenset(
        {
            BOZP_COORDINATION_STATUS_DRAFT,
        }
    ),
}

# Akce UI: (from, to) → (action_id, tlačítko, vyžaduje citlivé potvrzení)
BOZP_COORDINATION_LIFECYCLE_ACTIONS = (
    (
        BOZP_COORDINATION_STATUS_DRAFT,
        BOZP_COORDINATION_STATUS_READY,
        "prepare",
        "Připravit k vydání",
        False,
    ),
    (
        BOZP_COORDINATION_STATUS_DRAFT,
        BOZP_COORDINATION_STATUS_ARCHIVED,
        "archive",
        "Archivovat",
        False,
    ),
    (
        BOZP_COORDINATION_STATUS_READY,
        BOZP_COORDINATION_STATUS_DRAFT,
        "return_to_draft",
        "Vrátit k dopracování",
        False,
    ),
    (
        BOZP_COORDINATION_STATUS_READY,
        BOZP_COORDINATION_STATUS_ISSUED,
        "issue",
        "Vydat",
        False,
    ),
    (
        BOZP_COORDINATION_STATUS_READY,
        BOZP_COORDINATION_STATUS_ARCHIVED,
        "archive",
        "Archivovat",
        False,
    ),
    (
        BOZP_COORDINATION_STATUS_ISSUED,
        BOZP_COORDINATION_STATUS_COMPLETED,
        "complete",
        "Ukončit",
        False,
    ),
    (
        BOZP_COORDINATION_STATUS_ISSUED,
        BOZP_COORDINATION_STATUS_DRAFT,
        "return_to_draft",
        "Vrátit k dopracování",
        True,
    ),
    (
        BOZP_COORDINATION_STATUS_ISSUED,
        BOZP_COORDINATION_STATUS_ARCHIVED,
        "archive",
        "Archivovat",
        False,
    ),
    (
        BOZP_COORDINATION_STATUS_COMPLETED,
        BOZP_COORDINATION_STATUS_DRAFT,
        "reopen",
        "Znovu otevřít",
        True,
    ),
    (
        BOZP_COORDINATION_STATUS_COMPLETED,
        BOZP_COORDINATION_STATUS_ARCHIVED,
        "archive",
        "Archivovat",
        False,
    ),
    (
        BOZP_COORDINATION_STATUS_ARCHIVED,
        BOZP_COORDINATION_STATUS_DRAFT,
        "restore",
        "Obnovit",
        True,
    ),
)

# Stavy, u kterých přechod vyžaduje kontrolu protokolovým builderem.
BOZP_COORDINATION_STATUSES_REQUIRING_PROTOCOL_CHECK = frozenset(
    {
        BOZP_COORDINATION_STATUS_READY,
        BOZP_COORDINATION_STATUS_ISSUED,
    }
)

TAB_BASICS = "Základní údaje"
TAB_EMPLOYERS = "Zúčastnění zaměstnavatelé"
TAB_PARTICIPANTS = "Účastníci schůzky"
TAB_COORDINATOR = "Koordinátor BOZP"

# Ruční koordinátor – výběr organizace (UX-COORD-4c).
COORDINATOR_MANUAL_OTHER_ORGANIZATION = "__other_organization__"
COORDINATOR_MANUAL_OTHER_ORGANIZATION_LABEL = "Jiná organizace"
TAB_WORKPLACES = "Místa výkonu práce"
TAB_EMPLOYER_ACTIVITIES = "Činnosti na pracovišti"
TAB_MEASURES = "Dohoda a pravidla BOZP"

# UX-COORD-9a – pevné části dohody a společná pravidla.
AGREEMENT_SECTION_TITLE = "Dohoda o koordinaci BOZP"
COMMON_RULES_SECTION_TITLE = "Společná pravidla BOZP"
AGREEMENT_UI_SECTION_TITLE = "Dohoda o koordinaci"

AGREEMENT_PART_WORK_INTENT = (
    "Informování o záměru provádění prací a pohybu zaměstnanců / techniky "
    "na pracovišti"
)
AGREEMENT_PART_MUTUAL_RISKS = "Vzájemné informování o rizicích"
AGREEMENT_PART_PPE = "Osobní ochranné pracovní prostředky"
AGREEMENT_PART_COORDINATOR = (
    "Stanovení koordinátora na pracovišti a další ustanovení dohody"
)
AGREEMENT_PART_CONTACTS = "Organizační zajištění a důležité kontakty"
AGREEMENT_PART_WORKPLACE_HANDOVER = "Předání pracoviště"
AGREEMENT_PART_EMERGENCIES = "Mimořádné události"
AGREEMENT_PART_FINAL = "Závěrečná ustanovení"

AGREEMENT_FIXED_PART_ORDER = (
    AGREEMENT_PART_WORK_INTENT,
    AGREEMENT_PART_MUTUAL_RISKS,
    AGREEMENT_PART_PPE,
    AGREEMENT_PART_COORDINATOR,
    AGREEMENT_PART_CONTACTS,
    AGREEMENT_PART_WORKPLACE_HANDOVER,
    AGREEMENT_PART_EMERGENCIES,
    AGREEMENT_PART_FINAL,
)
TAB_CONTACTS = "Důležité kontakty"
TAB_RISK_SUBMISSIONS = "Předání rizik dodavatelů"
TAB_PBP_ATTACHMENT = "Příloha PBP"

# UX-COORD-4d – klíče QSettings pro šířky sloupců.
COORD_HEADER_LIST = "coordination/list/header"
COORD_HEADER_EMPLOYERS = "coordination/employers/header"
COORD_HEADER_PARTICIPANTS = "coordination/participants/header"
COORD_HEADER_WORKPLACES = "coordination/workplaces/header"
COORD_HEADER_ACTIVITIES = "coordination/activities/header"
COORD_HEADER_MEASURES = "coordination/measures/header"
COORD_HEADER_CONTACTS = "coordination/contacts/header"
COORD_HEADER_RISKS = "coordination/risks/header"
COORD_HEADER_PBP = "coordination/pbp/header"

# Důležité kontakty (COORD-010 / UX-COORD-11).
CONTACT_TYPE_TECHNICAL = "technical_requirements"
CONTACT_TYPE_ORGANIZATIONAL = "organizational_requirements"
CONTACT_TYPE_WORK_START_END = "work_start_end_reporting"
CONTACT_TYPE_SHIFT_SUPERVISOR = "shift_supervisor"
CONTACT_TYPE_OTHER = "other"

# Legacy typy – pouze pro stávající záznamy (nelze nově vybrat).
CONTACT_TYPE_COORDINATION = "coordination"
CONTACT_TYPE_WORKPLACE_HANDOVER = "workplace_handover"
CONTACT_TYPE_OPERATION = "operation"
CONTACT_TYPE_FIRST_AID = "first_aid"
CONTACT_TYPE_FIRE = "fire"
CONTACT_TYPE_EMERGENCY = "emergency"

CONTACT_TYPES_SELECTABLE = (
    CONTACT_TYPE_TECHNICAL,
    CONTACT_TYPE_ORGANIZATIONAL,
    CONTACT_TYPE_WORK_START_END,
    CONTACT_TYPE_SHIFT_SUPERVISOR,
    CONTACT_TYPE_OTHER,
)

CONTACT_TYPES_DEPRECATED_FOR_NEW = frozenset(
    {
        CONTACT_TYPE_COORDINATION,
        CONTACT_TYPE_WORKPLACE_HANDOVER,
        CONTACT_TYPE_OPERATION,
        CONTACT_TYPE_FIRST_AID,
        CONTACT_TYPE_FIRE,
        CONTACT_TYPE_EMERGENCY,
    }
)

CONTACT_TYPES = CONTACT_TYPES_SELECTABLE + (
    CONTACT_TYPE_COORDINATION,
    CONTACT_TYPE_WORKPLACE_HANDOVER,
    CONTACT_TYPE_OPERATION,
    CONTACT_TYPE_FIRST_AID,
    CONTACT_TYPE_FIRE,
    CONTACT_TYPE_EMERGENCY,
)

DEFAULT_CONTACT_TYPE = CONTACT_TYPE_OTHER

CONTACT_TYPE_LABELS = {
    CONTACT_TYPE_TECHNICAL: "Technické požadavky",
    CONTACT_TYPE_ORGANIZATIONAL: "Organizační požadavky",
    CONTACT_TYPE_WORK_START_END: "Ohlášení zahájení a ukončení prací",
    CONTACT_TYPE_SHIFT_SUPERVISOR: "Kontakt na vedoucího směny",
    CONTACT_TYPE_OTHER: "Ostatní",
    CONTACT_TYPE_COORDINATION: "Koordinace BOZP",
    CONTACT_TYPE_WORKPLACE_HANDOVER: "Předání pracoviště",
    CONTACT_TYPE_OPERATION: "Provoz / práce",
    CONTACT_TYPE_FIRST_AID: "První pomoc",
    CONTACT_TYPE_FIRE: "Požár",
    CONTACT_TYPE_EMERGENCY: "Mimořádná událost",
}

DEFAULT_EMERGENCY_REPORTING = (
    "Každou mimořádnou událost neprodleně oznamte koordinátorovi BOZP "
    "a odpovědnému zástupci hlavního zaměstnavatele."
)

DEFAULT_ACCIDENT_REPORTING = (
    "Pracovní úraz bezodkladně oznamte vedoucímu zaměstnanci postiženého "
    "zaměstnavatele a koordinátorovi BOZP. Místo události zachovejte beze změny, "
    "pokud tomu nebrání záchrana osob nebo zabránění dalším škodám."
)

DEFAULT_FIRE_REPORTING = (
    "Při zjištění požáru postupujte podle požárních poplachových směrnic "
    "pracoviště a událost oznamte na stanovené ohlašovací místo."
)

DEFAULT_EVACUATION_INSTRUCTIONS = (
    "Při evakuaci opustíte pracoviště určenými únikovými cestami "
    "a shromáždíte se na stanoveném shromaždišti. Nevracejte se zpět "
    "bez pokynu odpovědné osoby."
)

# Organizační opatření (COORD-009).
MEASURE_CATEGORY_WORK_ORGANIZATION = "work_organization"
MEASURE_CATEGORY_PERSON_MOVEMENT = "person_movement"
MEASURE_CATEGORY_VEHICLE_MOVEMENT = "vehicle_movement"
MEASURE_CATEGORY_WORKPLACE_HANDOVER = "workplace_handover"
MEASURE_CATEGORY_WORK_PERMITS = "work_permits"
MEASURE_CATEGORY_COMMUNICATION = "communication"
MEASURE_CATEGORY_EMERGENCIES = "emergencies"
MEASURE_CATEGORY_PPE = "ppe"
MEASURE_CATEGORY_OTHER = "other"

MEASURE_CATEGORIES = (
    MEASURE_CATEGORY_WORK_ORGANIZATION,
    MEASURE_CATEGORY_PERSON_MOVEMENT,
    MEASURE_CATEGORY_VEHICLE_MOVEMENT,
    MEASURE_CATEGORY_WORKPLACE_HANDOVER,
    MEASURE_CATEGORY_WORK_PERMITS,
    MEASURE_CATEGORY_COMMUNICATION,
    MEASURE_CATEGORY_EMERGENCIES,
    MEASURE_CATEGORY_PPE,
    MEASURE_CATEGORY_OTHER,
)

# UX-COORD-9c – kategorie s vlastní částí formuláře / dohody; nelze nově vybrat.
MEASURE_CATEGORIES_DEPRECATED_FOR_NEW = frozenset(
    {
        MEASURE_CATEGORY_WORKPLACE_HANDOVER,
        MEASURE_CATEGORY_EMERGENCIES,
        MEASURE_CATEGORY_PPE,
    }
)

MEASURE_CATEGORIES_SELECTABLE = tuple(
    category
    for category in MEASURE_CATEGORIES
    if category not in MEASURE_CATEGORIES_DEPRECATED_FOR_NEW
)

DEFAULT_MEASURE_CATEGORY = MEASURE_CATEGORY_OTHER

MEASURE_CATEGORY_LABELS = {
    MEASURE_CATEGORY_WORK_ORGANIZATION: "Organizace práce",
    MEASURE_CATEGORY_PERSON_MOVEMENT: "Pohyb osob",
    MEASURE_CATEGORY_VEHICLE_MOVEMENT: "Pohyb vozidel",
    MEASURE_CATEGORY_WORKPLACE_HANDOVER: "Předávání pracoviště",
    MEASURE_CATEGORY_WORK_PERMITS: "Povolení prací",
    MEASURE_CATEGORY_COMMUNICATION: "Komunikace",
    MEASURE_CATEGORY_EMERGENCIES: "Mimořádné události",
    MEASURE_CATEGORY_PPE: "OOPP",
    MEASURE_CATEGORY_OTHER: "Ostatní",
}

# UX-COORD-9d – malá sada výchozích společných pravidel (ne stará obecná sada).
DEFAULT_COMMON_RULE_FOLLOW_COORDINATOR = "coord_rule_follow_coordinator"
DEFAULT_COMMON_RULE_KEEP_ESCAPE_ROUTES = "coord_rule_keep_escape_routes_clear"
DEFAULT_COMMON_RULE_PROTECTIVE_DEVICES = "coord_rule_protective_devices"
DEFAULT_COMMON_RULE_RESTRICTED_AREAS = "coord_rule_restricted_areas"
DEFAULT_COMMON_RULE_VEHICLE_PARKING = "coord_rule_vehicle_parking"

DEFAULT_COMMON_BOZP_RULES = (
    {
        "template_code": DEFAULT_COMMON_RULE_FOLLOW_COORDINATOR,
        "category": MEASURE_CATEGORY_COMMUNICATION,
        "title": "Dodržovat pokyny koordinátora BOZP.",
        "description": (
            "Všichni zúčastnění zaměstnavatelé a jejich zaměstnanci jsou povinni "
            "dodržovat pokyny koordinátora BOZP."
        ),
    },
    {
        "template_code": DEFAULT_COMMON_RULE_KEEP_ESCAPE_ROUTES,
        "category": MEASURE_CATEGORY_PERSON_MOVEMENT,
        "title": "Udržovat průjezdné únikové cesty.",
        "description": (
            "Únikové cesty, komunikace a východy musí být trvale volné a průjezdné; "
            "nesmí se na nich ukládat materiál ani technika."
        ),
    },
    {
        "template_code": DEFAULT_COMMON_RULE_PROTECTIVE_DEVICES,
        "category": MEASURE_CATEGORY_WORK_ORGANIZATION,
        "title": "Nepřemisťovat ochranná zařízení bez souhlasu.",
        "description": (
            "Ochranná zařízení, zábrany a značení se nesmí přemisťovat ani odstraňovat "
            "bez souhlasu odpovědné osoby hlavního zaměstnavatele."
        ),
    },
    {
        "template_code": DEFAULT_COMMON_RULE_RESTRICTED_AREAS,
        "category": MEASURE_CATEGORY_PERSON_MOVEMENT,
        "title": "Dodržovat zákaz vstupu do vyznačených prostor.",
        "description": (
            "Do prostor se zákazem vstupu nebo s omezeným přístupem smí vstupovat "
            "pouze osoby k tomu oprávněné a vybavené."
        ),
    },
    {
        "template_code": DEFAULT_COMMON_RULE_VEHICLE_PARKING,
        "category": MEASURE_CATEGORY_VEHICLE_MOVEMENT,
        "title": "Parkovat vozidla pouze na určených místech.",
        "description": (
            "Vozidla a pracovní stroje lze odstavovat pouze na určených místech tak, "
            "aby nebránila provozu, přístupu ani úniku osob."
        ),
    },
)

DEFAULT_COMMON_BOZP_RULE_CODES = tuple(
    item["template_code"] for item in DEFAULT_COMMON_BOZP_RULES
)

COORDINATION_PBP_INTRO_TEXT = (
    "Dodržujte následující pravidla bezpečné práce. "
    "Jejich nedodržení může vést ke vzniku pracovního úrazu nebo mimořádné události."
)

COORDINATION_PBP_INFO_TEXT = (
    "Dodavatel je povinen před zahájením prací předat hlavnímu zaměstnavateli "
    "informace o rizicích vznikajících při jeho činnosti a o přijatých opatřeních."
)

ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP = "main_employer_pbp"

# Předání rizik hlavního zaměstnavatele (COORD-006 / budoucí export).
MAIN_EMPLOYER_RISK_HANDOVER_METHOD = "attachment"
MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE = (
    "Pravidla bezpečné práce a informace o rizicích hlavního zaměstnavatele"
)
MAIN_EMPLOYER_RISK_HANDOVER_PROTOCOL_TEXT = (
    "Hlavní zaměstnavatel předal zúčastněným zaměstnavatelům informace "
    "o rizicích a pravidlech bezpečné práce formou přílohy tohoto protokolu."
)
CONTRACTOR_RISK_COMMITMENT_PROTOCOL_TEXT = (
    "Zúčastněný zaměstnavatel se zavazuje před zahájením prací předat hlavnímu "
    "zaměstnavateli písemnou informaci o rizicích vznikajících při jeho činnosti "
    "a o přijatých opatřeních."
)

RISK_SUBMISSION_METHOD_ATTACHMENT = "attachment"
RISK_SUBMISSION_METHOD_EMAIL = "email"
RISK_SUBMISSION_METHOD_PAPER = "paper"
RISK_SUBMISSION_METHOD_DATA_BOX = "data_box"
RISK_SUBMISSION_METHOD_OTHER = "other"
RISK_SUBMISSION_METHOD_NOT_SUBMITTED = "not_submitted"

RISK_SUBMISSION_METHODS = (
    RISK_SUBMISSION_METHOD_NOT_SUBMITTED,
    RISK_SUBMISSION_METHOD_ATTACHMENT,
    RISK_SUBMISSION_METHOD_EMAIL,
    RISK_SUBMISSION_METHOD_PAPER,
    RISK_SUBMISSION_METHOD_DATA_BOX,
    RISK_SUBMISSION_METHOD_OTHER,
)

RISK_SUBMISSION_METHOD_LABELS = {
    RISK_SUBMISSION_METHOD_NOT_SUBMITTED: "Nepředáno",
    RISK_SUBMISSION_METHOD_ATTACHMENT: "Příloha",
    RISK_SUBMISSION_METHOD_EMAIL: "E-mail",
    RISK_SUBMISSION_METHOD_PAPER: "Papírově",
    RISK_SUBMISSION_METHOD_DATA_BOX: "Datová schránka",
    RISK_SUBMISSION_METHOD_OTHER: "Jinak",
}

RISK_HANDOVER_STATUS_NOT_SUBMITTED = "not_submitted"
RISK_HANDOVER_STATUS_WITHOUT_ATTACHMENT = "submitted_without_attachment"
RISK_HANDOVER_STATUS_WITH_ATTACHMENT = "submitted_with_attachment"
RISK_HANDOVER_STATUS_MAIN = "main_employer"

RISK_HANDOVER_STATUS_LABELS = {
    RISK_HANDOVER_STATUS_NOT_SUBMITTED: "Nepředáno",
    RISK_HANDOVER_STATUS_WITHOUT_ATTACHMENT: "Předáno bez přílohy",
    RISK_HANDOVER_STATUS_WITH_ATTACHMENT: "Předáno – příloha uložena",
    RISK_HANDOVER_STATUS_MAIN: "—",
}

ATTACHMENT_TYPE_CONTRACTOR_RISKS = "contractor_risks"
ATTACHMENT_TYPE_OTHER = "other"

ATTACHMENT_TYPES = (
    ATTACHMENT_TYPE_CONTRACTOR_RISKS,
    ATTACHMENT_TYPE_OTHER,
    ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
)

ATTACHMENT_TYPE_LABELS = {
    ATTACHMENT_TYPE_CONTRACTOR_RISKS: "Rizika dodavatele",
    ATTACHMENT_TYPE_OTHER: "Jiná příloha",
    ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP: "Příloha PBP hlavního zaměstnavatele",
}

COORDINATION_ATTACHMENT_ALLOWED_SUFFIXES = (
    ".pdf",
    ".docx",
    ".odt",
    ".xlsx",
    ".ods",
    ".jpg",
    ".jpeg",
    ".png",
)

COORDINATION_EMPLOYER_TYPE_MAIN = "main"
COORDINATION_EMPLOYER_TYPE_PARTICIPANT = "participant"

COORDINATION_EMPLOYER_TYPES = (
    COORDINATION_EMPLOYER_TYPE_MAIN,
    COORDINATION_EMPLOYER_TYPE_PARTICIPANT,
)

COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE = "employee"
COORDINATION_PARTICIPANT_SOURCE_MANUAL = "manual"

COORDINATION_PARTICIPANT_SOURCE_TYPES = (
    COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE,
    COORDINATION_PARTICIPANT_SOURCE_MANUAL,
)

EMP_COL_ID = 0
EMP_COL_ABBREVIATION = 1
EMP_COL_NAME = 2
EMP_COL_ICO = 3
EMP_COL_IS_MAIN = 4
EMP_COL_RISK_STATUS = 5
EMP_COL_ACTIVE = 6
EMP_COLUMN_COUNT = 7

EMPLOYER_TABLE_HEADERS = [
    "ID",
    "Zkratka",
    "Název",
    "IČO",
    "Hlavní zaměstnavatel",
    "Předání rizik",
    "Aktivní",
]

WP_COL_ID = 0
WP_COL_OPERATION = 1
WP_COL_WORKPLACE = 2
WP_COL_PART = 3
WP_COL_NOTE = 4
WP_COL_ACTIVE = 5
WP_COLUMN_COUNT = 6

WORKPLACE_TABLE_HEADERS = [
    "ID",
    "Provoz",
    "Pracoviště",
    "Část pracoviště",
    "Poznámka",
    "Aktivní",
]

ACT_COL_ID = 0
ACT_COL_EMPLOYER = 1
ACT_COL_NAME = 2
ACT_COL_PLACE = 3
ACT_COL_FROM = 4
ACT_COL_TO = 5
ACT_COL_ACTIVE = 6
ACT_COLUMN_COUNT = 7

ACTIVITY_TABLE_HEADERS = [
    "ID",
    "Zaměstnavatel",
    "Činnost",
    "Místo výkonu práce",
    "Od",
    "Do",
    "Aktivní",
]

MSR_COL_ID = 0
MSR_COL_CATEGORY = 1
MSR_COL_TITLE = 2
MSR_COL_DESCRIPTION = 3
MSR_COL_ACTIVE = 4
MSR_COLUMN_COUNT = 5

MEASURE_TABLE_HEADERS = [
    "ID",
    "Kategorie",
    "Krátký název",
    "Text opatření",
    "Aktivní",
]

MEASURE_EDITOR_HELP_TEXT = (
    "Krátký název slouží pro přehled v tabulce.\n"
    "Do pole Text opatření napište celý text určený do protokolu."
)

CTC_COL_ID = 0
CTC_COL_TYPE = 1
CTC_COL_NAME = 2
CTC_COL_ROLE = 3
CTC_COL_PHONE = 4
CTC_COL_EMAIL = 5
CTC_COL_ACTIVE = 6
CTC_COLUMN_COUNT = 7

CONTACT_TABLE_HEADERS = [
    "ID",
    "Typ kontaktu",
    "Jméno",
    "Funkce / role",
    "Telefon",
    "E-mail",
    "Aktivní",
]

ATT_COL_ID = 0
ATT_COL_FILENAME = 1
ATT_COL_TYPE = 2
ATT_COL_DESCRIPTION = 3
ATT_COL_ACTIVE = 4
ATT_COLUMN_COUNT = 5

ATTACHMENT_TABLE_HEADERS = [
    "ID",
    "Název přílohy",
    "Typ",
    "Popis",
    "Aktivní",
]

PART_COL_ID = 0
PART_COL_EMPLOYER = 1
PART_COL_FULL_NAME = 2
PART_COL_ROLE = 3
PART_COL_PHONE = 4
PART_COL_EMAIL = 5
PART_COL_ACTIVE = 6
PART_COLUMN_COUNT = 7

PARTICIPANT_TABLE_HEADERS = [
    "ID",
    "Zaměstnavatel",
    "Jméno a příjmení",
    "Funkce / role",
    "Telefon",
    "E-mail",
    "Aktivní",
]

COL_ID = 0
COL_NUMBER = 1
COL_MEETING_DATE = 2
COL_PLACE = 3
COL_SUBJECT = 4
COL_STATUS = 5
COL_VALIDITY = 6
COL_PBP = 7
COLUMN_COUNT = 8

TABLE_HEADERS = [
    "ID",
    "Číslo",
    "Datum schůzky",
    "Místo",
    "Název akce",
    "Stav",
    "Platnost",
    "Příloha PBP",
]

# Popisky editoru / validací / exportů (UX-COORD-1).
LABEL_MEETING_DATE = "Datum schůzky"
LABEL_MEETING_PLACE = "Místo schůzky"
LABEL_ACTION_NAME = "Název akce"
SUBJECT_REQUIRED_MESSAGE = "Název akce je povinný."

VALIDITY_STATE_VALID = "valid"
VALIDITY_STATE_EXPIRING = "expiring"
VALIDITY_STATE_EXPIRED = "expired"

VALIDITY_STATES = (
    VALIDITY_STATE_VALID,
    VALIDITY_STATE_EXPIRING,
    VALIDITY_STATE_EXPIRED,
)

VALIDITY_STATE_LABELS = {
    VALIDITY_STATE_VALID: "Platná",
    VALIDITY_STATE_EXPIRING: "Končí brzy",
    VALIDITY_STATE_EXPIRED: "Po platnosti",
}

VALIDITY_STATE_COLORS = {
    VALIDITY_STATE_VALID: "#2e7d32",
    VALIDITY_STATE_EXPIRING: "#ef6c00",
    VALIDITY_STATE_EXPIRED: "#c62828",
}

VALIDITY_WARNING_DAYS = 30

VALIDITY_FILTER_ALL = "all"
VALIDITY_FILTER_VALID = "valid"
VALIDITY_FILTER_EXPIRING = "expiring"
VALIDITY_FILTER_EXPIRED = "expired"

VALIDITY_FILTER_LABELS = {
    VALIDITY_FILTER_ALL: "Všechny",
    VALIDITY_FILTER_VALID: "Platné",
    VALIDITY_FILTER_EXPIRING: "Končící",
    VALIDITY_FILTER_EXPIRED: "Po platnosti",
}

# Aktuálnost přílohy PBP (COORD-007a) – dynamicky, neukládá se do DB.
PBP_FRESHNESS_CURRENT = "current"
PBP_FRESHNESS_NEEDS_UPDATE = "needs_update"
PBP_FRESHNESS_MISSING = "missing"
PBP_FRESHNESS_UNVERIFIABLE = "unverifiable"
PBP_FRESHNESS_SKIPPED = "skipped"

PBP_FRESHNESS_STATES = (
    PBP_FRESHNESS_CURRENT,
    PBP_FRESHNESS_NEEDS_UPDATE,
    PBP_FRESHNESS_MISSING,
    PBP_FRESHNESS_UNVERIFIABLE,
    PBP_FRESHNESS_SKIPPED,
)

PBP_FRESHNESS_LABELS = {
    PBP_FRESHNESS_CURRENT: "Aktuální",
    PBP_FRESHNESS_NEEDS_UPDATE: "Vyžaduje aktualizaci",
    PBP_FRESHNESS_MISSING: "Nevytvořena",
    PBP_FRESHNESS_UNVERIFIABLE: "Nelze ověřit",
    PBP_FRESHNESS_SKIPPED: "—",
}

PBP_FRESHNESS_DETAIL_MESSAGES = {
    PBP_FRESHNESS_CURRENT: "Příloha je aktuální.",
    PBP_FRESHNESS_NEEDS_UPDATE: (
        "Příloha neodpovídá současným údajům v Registru rizik."
    ),
    PBP_FRESHNESS_MISSING: "Příloha dosud nebyla vytvořena.",
    PBP_FRESHNESS_UNVERIFIABLE: "Aktuálnost nelze ověřit.",
    PBP_FRESHNESS_SKIPPED: "Kontrola se u ukončené koordinace neprovádí.",
}

PBP_FRESHNESS_TOOLTIPS = {
    PBP_FRESHNESS_CURRENT: "Hash přílohy odpovídá současnému obsahu Registru rizik.",
    PBP_FRESHNESS_NEEDS_UPDATE: (
        "Obsah Registru rizik se změnil – přílohu je třeba aktualizovat."
    ),
    PBP_FRESHNESS_MISSING: "Pro koordinaci ještě nebyla vytvořena příloha PBP.",
    PBP_FRESHNESS_UNVERIFIABLE: (
        "Nelze sestavit aktuální obsah (např. chybí aktivní místa nebo platná PBP)."
    ),
    PBP_FRESHNESS_SKIPPED: (
        "Kontrola se neprovádí u neaktivních, archivovaných nebo ukončených koordinací."
    ),
}

PBP_FRESHNESS_COLORS = {
    PBP_FRESHNESS_CURRENT: "#2e7d32",
    PBP_FRESHNESS_NEEDS_UPDATE: "#ef6c00",
    PBP_FRESHNESS_MISSING: "#c62828",
    PBP_FRESHNESS_UNVERIFIABLE: "#546e7a",
    PBP_FRESHNESS_SKIPPED: "#9e9e9e",
}

PBP_FILTER_ALL = "all"
PBP_FILTER_CURRENT = "current"
PBP_FILTER_NEEDS_UPDATE = "needs_update"
PBP_FILTER_MISSING = "missing"
PBP_FILTER_UNVERIFIABLE = "unverifiable"

PBP_FILTER_LABELS = {
    PBP_FILTER_ALL: "Všechny",
    PBP_FILTER_CURRENT: "Aktuální",
    PBP_FILTER_NEEDS_UPDATE: "Vyžadují aktualizaci",
    PBP_FILTER_MISSING: "Bez přílohy",
    PBP_FILTER_UNVERIFIABLE: "Nelze ověřit",
}

# Náhled koordinačního protokolu (COORD-011a).
PROTOCOL_WARNING_SEVERITY_INFO = "info"
PROTOCOL_WARNING_SEVERITY_WARNING = "warning"
PROTOCOL_WARNING_SEVERITY_CRITICAL = "critical"

PROTOCOL_WARNING_SEVERITIES = (
    PROTOCOL_WARNING_SEVERITY_INFO,
    PROTOCOL_WARNING_SEVERITY_WARNING,
    PROTOCOL_WARNING_SEVERITY_CRITICAL,
)

PROTOCOL_WARNING_MISSING_COORDINATOR = "missing_coordinator"
PROTOCOL_WARNING_MISSING_WORKPLACE = "missing_workplace"
PROTOCOL_WARNING_MISSING_SUBJECT = "missing_subject"
PROTOCOL_WARNING_MISSING_MEETING_DATE = "missing_meeting_date"
PROTOCOL_WARNING_MISSING_MEETING_PLACE = "missing_meeting_place"
PROTOCOL_WARNING_MISSING_ACTIVE_EMPLOYER = "missing_active_employer"
PROTOCOL_WARNING_EMPLOYER_WITHOUT_ACTIVITY = "employer_without_activity"
PROTOCOL_WARNING_MISSING_PBP_SNAPSHOT = "missing_pbp_snapshot"
PROTOCOL_WARNING_STALE_PBP_SNAPSHOT = "stale_pbp_snapshot"
PROTOCOL_WARNING_RISKS_NOT_SUBMITTED = "contractor_risks_not_submitted"
PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT = "contractor_risks_without_attachment"
PROTOCOL_WARNING_MISSING_MEASURES = "missing_measures"
PROTOCOL_WARNING_EXPIRED_VALIDITY = "expired_validity"
PROTOCOL_WARNING_INACTIVE_OR_ARCHIVED = "inactive_or_archived"

