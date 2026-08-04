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

AGENDA_ITEM_STATUS_READY = "Připraveno"
AGENDA_ITEM_STATUS_DISCUSSED = "Projednáno"
AGENDA_ITEM_STATUS_POSTPONED = "Odloženo"

AGENDA_ITEM_STATUSES = (
    AGENDA_ITEM_STATUS_READY,
    AGENDA_ITEM_STATUS_DISCUSSED,
    AGENDA_ITEM_STATUS_POSTPONED,
)

DEFAULT_AGENDA_ITEM_STATUS = AGENDA_ITEM_STATUS_READY

AGENDA_ITEM_STATUS_ICONS = {
    AGENDA_ITEM_STATUS_READY: "🟡",
    AGENDA_ITEM_STATUS_DISCUSSED: "🟢",
    AGENDA_ITEM_STATUS_POSTPONED: "🔵",
}

AGENDA_ITEM_STATUS_MENU_TITLE = "Označit jako"

AGENDA_ITEM_DIALOG_TITLE = "Bod jednání"  # legacy – dialog zrušen v MEETINGS-2c
AGENDA_ITEMS_SECTION = "Body jednání"
AGENDA_ITEMS_EMPTY = "Zatím nejsou evidovány žádné body jednání."
AGENDA_SELECT_ITEM_MESSAGE = "Vyberte bod jednání."

ACTION_ADD_AGENDA_ITEM = "Přidat"
ACTION_EDIT = "Upravit"
ACTION_REMOVE = "Odebrat"
ACTION_MOVE_UP = "Nahoru"
ACTION_MOVE_DOWN = "Dolů"

SECTION_ITEM_TASKS = "Úkoly"
ACTION_ADD_TASK = "Přidat úkol"
ACTION_OPEN_TASK = "Otevřít úkol"
ACTION_UNLINK_TASK = "Odpojit od bodu"
SAVE_MEETING_BEFORE_TASK_MESSAGE = "Nejprve uložte schůzku."
AGENDA_ITEM_CHECK_PREFIX = "item:"

# Legacy MEETINGS-1d (sekce na úrovni schůzky zrušeny v MEETINGS-2d)
SECTION_CONCLUSION_TASKS = "Úkoly ze závěrů"
SECTION_LINKED_TASKS = "Navázané úkoly"
ACTION_CREATE_TASK = "Vytvořit úkol"
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
