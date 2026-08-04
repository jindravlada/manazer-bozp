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

# Společný filtr stavu (jako Zobrazit v Úkolech).
STATUS_MODE_ACTIVE = "Aktivní"
STATUS_MODE_DONE = "Splněné"
STATUS_MODE_CANCELLED = "Zrušené"
STATUS_MODE_PLANNED = "Naplánované"
STATUS_MODE_HELD = "Proběhlé"
STATUS_MODE_CLOSED = "Uzavřené"
STATUS_MODE_ALL = "Vše"

DEFAULT_STATUS_MODE = STATUS_MODE_ACTIVE

STATUS_MODES_TASKS_ONLY = (
    STATUS_MODE_ACTIVE,
    STATUS_MODE_DONE,
    STATUS_MODE_CANCELLED,
    STATUS_MODE_ALL,
)

STATUS_MODES_MEETINGS_ONLY = (
    STATUS_MODE_PLANNED,
    STATUS_MODE_HELD,
    STATUS_MODE_CLOSED,
    STATUS_MODE_CANCELLED,
    STATUS_MODE_ALL,
)

STATUS_MODES_BOTH = (
    STATUS_MODE_ACTIVE,
    STATUS_MODE_DONE,
    STATUS_MODE_PLANNED,
    STATUS_MODE_HELD,
    STATUS_MODE_CLOSED,
    STATUS_MODE_CANCELLED,
    STATUS_MODE_ALL,
)

ACTION_NEW_TASK = "Nový úkol"
ACTION_NEW_MEETING = "Nová událost"
ACTION_OPEN = "Otevřít"
ACTION_EDIT = "Upravit"
ACTION_AGENDA = "Agenda"

# Stejná legenda jako v modulu Úkoly.
ROW_LEGEND = (
    "Řádky: červená = po termínu, žlutá = čeká na kontrolu, "
    "zelená = ukončeno, šedá = zrušeno"
)

EMPTY_STATE_TEXT = "Nejsou evidovány žádné položky agendy odpovídající filtrům."
SELECT_ITEM_MESSAGE = "Vyberte položku agendy."
ITEM_NOT_FOUND_MESSAGE = "Záznam nebyl nalezen."

# Pořadí sloupců blízké Úkolům: Název → Termín → osoba → Stav → Zdroj → Typ.
COL_TITLE = 0
COL_DUE = 1
COL_PERSON = 2
COL_STATUS = 3
COL_SOURCE = 4
COL_TYPE = 5

COLUMN_HEADERS = [
    "Název",
    "Termín",
    "Odpovědná osoba / Organizátor",
    "Stav",
    "Zdroj",
    "Typ",
]

SOURCE_LABEL_MEETING = "Události"

# Stejné barvy jako TaskTable.
ROW_STATE_ACTIVE = "active"
ROW_STATE_OVERDUE = "overdue"
ROW_STATE_WAITING = "waiting_check"
ROW_STATE_DONE = "done"
ROW_STATE_CANCELED = "canceled"

ROW_COLORS = {
    ROW_STATE_ACTIVE: "#ffffff",
    ROW_STATE_OVERDUE: "#ffe0e0",
    ROW_STATE_WAITING: "#fff2b3",
    ROW_STATE_DONE: "#d9f2d9",
    ROW_STATE_CANCELED: "#eeeeee",
}
