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
