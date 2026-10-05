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
