"""Konstanty modulu Schůzky (MEETINGS-1a)."""

MODULE_KEY = "schuzky"
MODULE_NAME = "Schůzky"
DIALOG_WINDOW_TITLE = "Schůzka"
LIST_WINDOW_TITLE = "Schůzky"

STATUS_PLANNED = "Naplánováno"
STATUS_HELD = "Proběhlo"
STATUS_CLOSED = "Uzavřeno"
STATUS_CANCELLED = "Zrušeno"

MEETING_STATUSES = (
    STATUS_PLANNED,
    STATUS_HELD,
    STATUS_CLOSED,
    STATUS_CANCELLED,
)

DEFAULT_MEETING_STATUS = STATUS_PLANNED

END_BEFORE_START_MESSAGE = "Konec schůzky nesmí být dříve než začátek."

TAB_MEETING = "Schůzka"
TAB_MINUTES = "Záznam z jednání"  # legacy – nahrazeno TAB_DISCUSSION
TAB_DISCUSSION = "Jednání"

AGENDA_ITEM_DIALOG_TITLE = "Bod jednání"
AGENDA_ITEMS_SECTION = "Body jednání"
AGENDA_ITEMS_EMPTY = "Zatím nejsou evidovány žádné body jednání."
AGENDA_SELECT_ITEM_MESSAGE = "Vyberte bod jednání."

ACTION_ADD_AGENDA_ITEM = "Přidat bod"
ACTION_EDIT = "Upravit"
ACTION_REMOVE = "Odebrat"
ACTION_MOVE_UP = "Nahoru"
ACTION_MOVE_DOWN = "Dolů"

SAVE_MEETING_BEFORE_TASK_MESSAGE = "Nejprve uložte schůzku."
SECTION_CONCLUSION_TASKS = "Úkoly ze závěrů"
SECTION_LINKED_TASKS = "Navázané úkoly"
ACTION_CREATE_TASK = "Vytvořit úkol"
ACTION_OPEN_TASK = "Otevřít úkol"

CONCLUSION_CHECK_PREFIX = "concl:"

COL_ID = 0
COL_STARTS_AT = 1
COL_TITLE = 2
COL_LOCATION = 3
COL_ORGANIZER = 4
COL_STATUS = 5

COLUMN_HEADERS = [
    "ID",
    "Datum a čas",
    "Název",
    "Místo",
    "Organizátor",
    "Stav",
]
