"""Konstanty modulu Koordinace BOZP."""

MODULE_KEY = "koordinace_bozp"
MODULE_NAME = "Koordinace BOZP"
MODULE_DESCRIPTION = (
    "Evidence koordinačních schůzek BOZP podle § 101 odst. 3 zákoníku práce."
)

DIALOG_WINDOW_TITLE = "Koordinace BOZP"

BOZP_COORDINATION_STATUS_DRAFT = "draft"
BOZP_COORDINATION_STATUS_COMPLETED = "completed"
BOZP_COORDINATION_STATUS_ARCHIVED = "archived"

BOZP_COORDINATION_STATUSES = (
    BOZP_COORDINATION_STATUS_DRAFT,
    BOZP_COORDINATION_STATUS_COMPLETED,
    BOZP_COORDINATION_STATUS_ARCHIVED,
)

DEFAULT_BOZP_COORDINATION_STATUS = BOZP_COORDINATION_STATUS_DRAFT

BOZP_COORDINATION_STATUS_LABELS = {
    BOZP_COORDINATION_STATUS_DRAFT: "Rozpracováno",
    BOZP_COORDINATION_STATUS_COMPLETED: "Dokončeno",
    BOZP_COORDINATION_STATUS_ARCHIVED: "Archivováno",
}

TAB_BASICS = "Základní údaje"
TAB_EMPLOYERS = "Zúčastnění zaměstnavatelé"
TAB_PARTICIPANTS = "Účastníci schůzky"
TAB_COORDINATOR = "Koordinátor BOZP"
TAB_WORKPLACES = "Místa výkonu práce"
TAB_RISK_SUBMISSIONS = "Předání rizik dodavatelů"
TAB_PBP_ATTACHMENT = "Příloha PBP"

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

ATT_COL_ID = 0
ATT_COL_FILENAME = 1
ATT_COL_TYPE = 2
ATT_COL_DESCRIPTION = 3
ATT_COL_ACTIVE = 4
ATT_COLUMN_COUNT = 5

ATTACHMENT_TABLE_HEADERS = [
    "ID",
    "Soubor",
    "Typ",
    "Popis",
    "Aktivní",
]

PART_COL_ID = 0
PART_COL_FULL_NAME = 1
PART_COL_ROLE = 2
PART_COL_PHONE = 3
PART_COL_EMAIL = 4
PART_COL_ACTIVE = 5
PART_COLUMN_COUNT = 6

PARTICIPANT_TABLE_HEADERS = [
    "ID",
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
COLUMN_COUNT = 7

TABLE_HEADERS = [
    "ID",
    "Číslo",
    "Datum koordinační schůzky",
    "Místo",
    "Předmět koordinace",
    "Stav",
    "Platnost",
]

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
