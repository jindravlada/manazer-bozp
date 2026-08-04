"""Konstanty modulu Agenda (společný pohled)."""

MODULE_KEY = "agenda"
MODULE_NAME = "Agenda"
LIST_WINDOW_TITLE = "Agenda"

ITEM_TYPE_TASK = "task"
ITEM_TYPE_MEETING = "meeting"

TYPE_LABEL_TASK = "Úkol"
TYPE_LABEL_MEETING = "Událost"

TYPE_FILTER_TASKS = "Úkoly"
TYPE_FILTER_MEETINGS = "Události"

# Filtry stavu – zobrazené názvy (mapování na zdrojové stavy je ve službě).
STATUS_FILTER_TASK_OPEN = "Otevřený"
STATUS_FILTER_TASK_DONE = "Splněný"
STATUS_FILTER_TASK_CANCELLED = "Zrušený"
STATUS_FILTER_MEETING_PLANNED = "Naplánováno"
STATUS_FILTER_MEETING_HELD = "Proběhlo"
STATUS_FILTER_MEETING_CLOSED = "Uzavřeno"
STATUS_FILTER_MEETING_CANCELLED = "Zrušeno"
STATUS_FILTER_OVERDUE = "Po termínu"

TASK_STATUS_FILTERS = (
    STATUS_FILTER_TASK_OPEN,
    STATUS_FILTER_TASK_DONE,
    STATUS_FILTER_TASK_CANCELLED,
    STATUS_FILTER_OVERDUE,
)

MEETING_STATUS_FILTERS = (
    STATUS_FILTER_MEETING_PLANNED,
    STATUS_FILTER_MEETING_HELD,
    STATUS_FILTER_MEETING_CLOSED,
    STATUS_FILTER_MEETING_CANCELLED,
    STATUS_FILTER_OVERDUE,
)

ACTION_NEW_TASK = "Nový úkol"
ACTION_NEW_MEETING = "Nová událost"
ACTION_OPEN = "Otevřít"
ACTION_EDIT = "Upravit"
ACTION_AGENDA = "Agenda"

# Výchozí filtr při otevření z pracovní plochy (aktivní + po termínu).
WORKSPACE_TASK_STATUS_FILTERS = (
    STATUS_FILTER_TASK_OPEN,
    STATUS_FILTER_OVERDUE,
)
WORKSPACE_MEETING_STATUS_FILTERS = (
    STATUS_FILTER_MEETING_PLANNED,
    STATUS_FILTER_OVERDUE,
)

EMPTY_STATE_TEXT = "Nejsou evidovány žádné položky agendy odpovídající filtrům."
SELECT_ITEM_MESSAGE = "Vyberte položku agendy."
ITEM_NOT_FOUND_MESSAGE = "Záznam nebyl nalezen."

COL_TYPE = 0
COL_DUE = 1
COL_TITLE = 2
COL_PERSON = 3
COL_STATUS = 4
COL_SOURCE = 5

COLUMN_HEADERS = [
    "Typ",
    "Termín",
    "Název",
    "Odpovědná osoba / Organizátor",
    "Stav",
    "Zdroj",
]

SOURCE_LABEL_MEETING = "Události"
