"""Konstanty Ročního plánu."""

MODULE_KEY = "rocni_plan"
MODULE_NAME = "Roční plán"

STATUS_PLANNED = "planned"
STATUS_VIA_TASK = "via_task"
STATUS_VIA_MEETING = "via_meeting"
STATUS_CANCELLED = "cancelled"

ITEM_STATUSES = (
    STATUS_PLANNED,
    STATUS_VIA_TASK,
    STATUS_VIA_MEETING,
    STATUS_CANCELLED,
)

DEFAULT_STATUS = STATUS_PLANNED

STATUS_LABELS = {
    STATUS_PLANNED: "Naplánováno",
    STATUS_VIA_TASK: "Řeší se úkolem",
    STATUS_VIA_MEETING: "Řeší se událostí",
    STATUS_CANCELLED: "Zrušeno",
}

SOURCE_MODULE_YEARLY_PLAN = "yearly_plan"

MIN_YEAR = 2000
MAX_YEAR = 2100

MONTH_NAMES = (
    "leden",
    "únor",
    "březen",
    "duben",
    "květen",
    "červen",
    "červenec",
    "srpen",
    "září",
    "říjen",
    "listopad",
    "prosinec",
)

TAB_YEARLY_PLAN = "Roční plán"

ACTION_NEW = "Nová položka"
ACTION_EDIT = "Upravit"
ACTION_CREATE_TASK = "Vytvořit úkol"
ACTION_CREATE_MEETING = "Vytvořit událost"
ACTION_MOVE = "Přesunout"
ACTION_CANCEL = "Zrušit"

DIALOG_TITLE_NEW = "Nová položka Ročního plánu"
DIALOG_TITLE_EDIT = "Položka Ročního plánu"
DIALOG_TITLE_MOVE = "Přesunout položku"

TAB_ITEM = "Položka"
TAB_MOVE_HISTORY = "Historie přesunů"

EMPTY_STATE_TEXT = "Nejsou evidovány žádné položky Ročního plánu pro zvolený měsíc."
ITEM_NOT_FOUND_MESSAGE = "Položka Ročního plánu nebyla nalezena."
TITLE_REQUIRED_MESSAGE = "Vyplňte název položky."
CANCEL_CONFIRM_MESSAGE = "Opravdu zrušit vybranou položku Ročního plánu?"
ALREADY_LINKED_MESSAGE = "Položka už má vazbu na Úkol nebo Událost."
CANCELLED_ACTION_MESSAGE = "Zrušenou položku nelze upravit touto akcí."

COL_ID = 0
COL_TITLE = 1
COL_STATUS = 2
COL_LINK = 3
COL_NOTE = 4

COLUMN_HEADERS = [
    "ID",
    "Název",
    "Stav",
    "Vazba",
    "Poznámka",
]

MOVE_HISTORY_HEADERS = [
    "Odkud",
    "Kam",
    "Datum přesunu",
]


def month_label(month: int) -> str:
    if 1 <= month <= 12:
        return MONTH_NAMES[month - 1]
    return str(month)


def format_year_month(year: int, month: int) -> str:
    name = month_label(month)
    return f"{name} {year}"


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def link_label(item) -> str:
    if getattr(item, "task_id", None):
        return f"Úkol #{item.task_id}"
    if getattr(item, "meeting_id", None):
        return f"Událost #{item.meeting_id}"
    return "—"
