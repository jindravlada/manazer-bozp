"""Konstanty modulu Testy."""

MODULE_KEY = "testy"
MODULE_NAME = "Testy"
MODULE_DESCRIPTION = (
    "Evidence zaměstnanců, příprava testů a evidence výsledků přezkoušení."
)
PAGE_SUBTITLE = MODULE_DESCRIPTION

ACTION_NEW = "Nový zaměstnanec"
ACTION_EDIT = "Upravit"
SHOW_INACTIVE_LABEL = "Zobrazit neaktivní"
STATUS_ACTIVE_LABEL = "Aktivní"
STATUS_INACTIVE_LABEL = "Neaktivní"
DIALOG_TITLE_NEW = "Nový zaměstnanec"
DIALOG_TITLE_EDIT = "Zaměstnanec"
SEARCH_PLACEHOLDER = "🔍 Hledat zaměstnance..."

COL_ID = 0
COL_PERSONAL_NUMBER = 1
COL_LAST_NAME = 2
COL_FIRST_NAME = 3
COL_ROLES = 4
COL_WORKPLACE = 5
COL_STATUS = 6

COLUMN_HEADERS = [
    "ID",
    "Osobní číslo",
    "Příjmení",
    "Jméno",
    "Funkce / role",
    "Provoz (pracoviště)",
    "Stav",
]

AGENDA_EMPLOYEES = "Zaměstnanci"
AGENDA_WRITTEN_TOPICS = "Okruhy otázek"

TOPIC_ACTION_NEW = "Nový okruh"
TOPIC_DIALOG_TITLE_NEW = "Nový okruh"
TOPIC_DIALOG_TITLE_EDIT = "Okruh"
TOPIC_SEARCH_PLACEHOLDER = "🔍 Hledat okruh..."

TOPIC_COL_ID = 0
TOPIC_COL_NAME = 1
TOPIC_COL_DESCRIPTION = 2
TOPIC_COL_STATUS = 3

TOPIC_COLUMN_HEADERS = [
    "ID",
    "Název",
    "Popis",
    "Stav",
]

AGENDA_QUESTIONS = "Otázky"
QUESTION_ACTION_NEW = "Nová otázka"
QUESTION_DIALOG_TITLE_NEW = "Nová otázka"
QUESTION_DIALOG_TITLE_EDIT = "Otázka"
QUESTION_SEARCH_PLACEHOLDER = "🔍 Hledat otázku..."
QUESTION_TOPIC_FILTER_ALL = "Všechny okruhy"
ANSWER_KIND_TEXT = "text"
ANSWER_KIND_IMAGE = "image"
ANSWER_KIND_TEXT_LABEL = "Textové"
ANSWER_KIND_IMAGE_LABEL = "Obrázkové"
ANSWER_KIND_SWITCH_CONFIRM = (
    "Přepnutí typu odpovědí vymaže již zadané odpovědi A, B a C. Pokračovat?"
)
ANSWER_LETTERS = ("A", "B", "C")

QUESTION_COL_ID = 0
QUESTION_COL_TEXT = 1
QUESTION_COL_TOPIC = 2
QUESTION_COL_KIND = 3
QUESTION_COL_STATUS = 4

QUESTION_COLUMN_HEADERS = [
    "ID",
    "Otázka",
    "Okruh",
    "Typ odpovědí",
    "Stav",
]

AGENDA_ORAL_TOPICS = "Ústní okruhy"
AGENDA_ORAL_QUESTIONS = "Ústní otázky"

ORAL_QUESTION_COL_ID = 0
ORAL_QUESTION_COL_TEXT = 1
ORAL_QUESTION_COL_TOPIC = 2
ORAL_QUESTION_COL_STATUS = 3

ORAL_QUESTION_COLUMN_HEADERS = [
    "ID",
    "Otázka",
    "Okruh",
    "Stav",
]

AGENDA_TESTS = "Testy"
TEST_ACTION_NEW = "Nový test"
TEST_DIALOG_TITLE_NEW = "Nový test"
TEST_DIALOG_TITLE_EDIT = "Test"
TEST_SEARCH_PLACEHOLDER = "🔍 Hledat test..."
PART_YES_LABEL = "Ano"
PART_NO_LABEL = "Ne"
DEFAULT_SECONDS_PER_QUESTION = 30

EXAMINER_MODE_NONE = "none"
EXAMINER_MODE_SINGLE = "single"
EXAMINER_MODE_COMMISSION = "commission"
EXAMINER_MODE_NONE_LABEL = "Bez zkoušejícího / komise"
EXAMINER_MODE_SINGLE_LABEL = "Jeden zkoušející"
EXAMINER_MODE_COMMISSION_LABEL = "Komise"
EXAMINER_MODES = (
    EXAMINER_MODE_NONE,
    EXAMINER_MODE_SINGLE,
    EXAMINER_MODE_COMMISSION,
)

VALIDITY_UNIT_MONTHS = "months"
VALIDITY_UNIT_YEARS = "years"
VALIDITY_UNIT_MONTHS_LABEL = "měsíce"
VALIDITY_UNIT_YEARS_LABEL = "roky"
VALIDITY_UNITS = (
    VALIDITY_UNIT_MONTHS,
    VALIDITY_UNIT_YEARS,
)

TEST_COL_ID = 0
TEST_COL_NAME = 1
TEST_COL_WRITTEN = 2
TEST_COL_ORAL = 3
TEST_COL_QUESTION_COUNT = 4
TEST_COL_VALIDITY = 5
TEST_COL_STATUS = 6

TEST_COLUMN_HEADERS = [
    "ID",
    "Název",
    "Písemná část",
    "Ústní část",
    "Počet otázek",
    "Platnost",
    "Stav",
]
