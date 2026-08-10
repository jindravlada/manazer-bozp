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

# Opakování ruční položky.
REPEAT_UNIT_NONE = "none"
REPEAT_UNIT_MONTHS = "months"
REPEAT_UNIT_YEARS = "years"

REPEAT_UNITS = (
    REPEAT_UNIT_NONE,
    REPEAT_UNIT_MONTHS,
    REPEAT_UNIT_YEARS,
)

DEFAULT_REPEAT_EVERY = 0
DEFAULT_REPEAT_UNIT = REPEAT_UNIT_NONE

REPEAT_UNIT_LABELS = {
    REPEAT_UNIT_NONE: "neopakovat",
    REPEAT_UNIT_MONTHS: "měsíců",
    REPEAT_UNIT_YEARS: "let",
}

# Typ termínu v měsíci.
DUE_KIND_NONE = "none"
DUE_KIND_DAY = "day"
DUE_KIND_FIRST_WORKING_DAY = "first_working_day"

DUE_KINDS = (
    DUE_KIND_NONE,
    DUE_KIND_DAY,
    DUE_KIND_FIRST_WORKING_DAY,
)

DEFAULT_DUE_KIND = DUE_KIND_NONE

DUE_KIND_LABELS = {
    DUE_KIND_NONE: "Bez konkrétního dne",
    DUE_KIND_DAY: "Konkrétní den",
    DUE_KIND_FIRST_WORKING_DAY: "První pracovní den",
}

STATUS_LABELS = {
    STATUS_PLANNED: "Naplánováno",
    STATUS_VIA_TASK: "Řeší se úkolem",
    STATUS_VIA_MEETING: "Řeší se událostí",
    STATUS_CANCELLED: "Zrušeno",
}

# Odvozené stavy (neukládají se do yearly_plan_items.status).
DISPLAY_PLANNED = STATUS_PLANNED
DISPLAY_VIA_TASK = STATUS_VIA_TASK
DISPLAY_VIA_MEETING = STATUS_VIA_MEETING
DISPLAY_DONE = "done"
DISPLAY_CANCELLED = STATUS_CANCELLED
DISPLAY_REST = "rest"

DISPLAY_STATUS_LABELS = {
    DISPLAY_PLANNED: "Naplánováno",
    DISPLAY_VIA_TASK: "Řeší se úkolem",
    DISPLAY_VIA_MEETING: "Řeší se událostí",
    DISPLAY_DONE: "Splněno",
    DISPLAY_CANCELLED: "Zrušeno",
    DISPLAY_REST: "Rest",
}

SOURCE_MODULE_YEARLY_PLAN = "yearly_plan"

MIN_YEAR = 2000
MAX_YEAR = 2100

# Výběr roku v Agendě → Roční plán (AGENDA-ANNUAL-PLAN-UX-1).
YEAR_COMBO_PAST_YEARS = 5
YEAR_COMBO_FUTURE_YEARS = 10
YEAR_COMBO_MAX_VISIBLE = 12

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
ACTION_MARK_MONTH_PROCESSED = "Měsíc zpracován"

DIALOG_TITLE_NEW = "Nová položka Ročního plánu"
DIALOG_TITLE_EDIT = "Položka Ročního plánu"
DIALOG_TITLE_MOVE = "Přesunout položku"

TAB_ITEM = "Položka"
TAB_MOVE_HISTORY = "Historie přesunů"

EMPTY_STATE_TEXT = "Nejsou evidovány žádné položky Ročního plánu pro zvolený měsíc."
ITEM_NOT_FOUND_MESSAGE = "Položka Ročního plánu nebyla nalezena."
TITLE_REQUIRED_MESSAGE = "Vyplňte název položky."
CANCEL_CONFIRM_MESSAGE = "Opravdu zrušit vybranou položku Ročního plánu?"
MARK_MONTH_PROCESSED_CONFIRM = (
    "Označit měsíc jako zpracovaný?\n\n"
    "Potvrzujete, že jste prošli plán tohoto měsíce a rozhodli jste, "
    "co budete dělat. Stavy jednotlivých položek se nemění."
)
ALREADY_LINKED_MESSAGE = "Položka už má vazbu na Úkol nebo Událost."
CANCELLED_ACTION_MESSAGE = "Zrušenou položku nelze upravit touto akcí."
MONTH_ALREADY_PROCESSED_MESSAGE = "Tento měsíc už je označen jako zpracovaný."

COL_ID = 0
COL_TITLE = 1
COL_STATUS = 2
COL_LINK = 3
COL_NOTE = 4
COL_SOURCE = 5

COLUMN_HEADERS = [
    "ID",
    "Název",
    "Stav",
    "Vazba",
    "Poznámka",
    "Zdroj",
]

ROW_KIND_MANUAL = "manual"
ROW_KIND_PERIODIC = "periodic"

SOURCE_LABEL_MANUAL = "Roční plán"
SOURCE_LABEL_PERIODIC = "Periodická činnost"

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


def format_processed_at(value) -> str:
    """Decentní zobrazení data zpracování měsíce."""
    if value is None:
        return ""
    if hasattr(value, "day") and hasattr(value, "month") and hasattr(value, "year"):
        return f"{value.day}. {value.month}. {value.year}"
    return str(value)


def month_planning_attention_title(year: int, month: int) -> str:
    return f"Zpracovat úkoly měsíce – {format_year_month(year, month)}"


def month_planning_source_id(year: int, month: int) -> int:
    return int(year) * 100 + int(month)


def status_label(status: str) -> str:
    return DISPLAY_STATUS_LABELS.get(status, STATUS_LABELS.get(status, status))


def link_label(item) -> str:
    if getattr(item, "task_id", None):
        return f"Úkol #{item.task_id}"
    if getattr(item, "meeting_id", None):
        return f"Událost #{item.meeting_id}"
    return "—"
