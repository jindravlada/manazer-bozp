"""Konstanty Periodických činností."""

MODULE_KEY = "periodicke_cinnosti"
MODULE_NAME = "Periodické činnosti"

# Přílohy patří ke konkrétnímu provedení (occurrence), ne k definici činnosti.
ENTITY_PERIODIC_OCCURRENCE = "periodic_occurrence"

PLACE_KIND_WORKPLACE = "workplace"
PLACE_KIND_ORGANIZATION = "organization"
PLACE_KIND_OTHER = "other"
PLACE_KIND_NONE = "none"

PLACE_KINDS = (
    PLACE_KIND_WORKPLACE,
    PLACE_KIND_ORGANIZATION,
    PLACE_KIND_OTHER,
    PLACE_KIND_NONE,
)

UNIT_DAYS = "days"
UNIT_WEEKS = "weeks"
UNIT_MONTHS = "months"
UNIT_YEARS = "years"

TIME_UNITS = (
    UNIT_DAYS,
    UNIT_WEEKS,
    UNIT_MONTHS,
    UNIT_YEARS,
)

NEXT_FROM_PLANNED = "planned"
NEXT_FROM_ACTUAL = "actual"

NEXT_FROM_VALUES = (
    NEXT_FROM_PLANNED,
    NEXT_FROM_ACTUAL,
)

DEFAULT_PLACE_KIND = PLACE_KIND_NONE
DEFAULT_REPEAT_EVERY = 1
DEFAULT_REPEAT_UNIT = UNIT_YEARS
DEFAULT_NOTIFY_EVERY = 0
DEFAULT_NOTIFY_UNIT = UNIT_DAYS
DEFAULT_NEXT_FROM = NEXT_FROM_PLANNED

PLACE_KIND_LABELS = {
    PLACE_KIND_WORKPLACE: "Provoz / pracoviště",
    PLACE_KIND_ORGANIZATION: "Celá organizace",
    PLACE_KIND_OTHER: "Jiné / mimo organizaci",
    PLACE_KIND_NONE: "Bez určení místa",
}

UNIT_LABELS = {
    UNIT_DAYS: "dny",
    UNIT_WEEKS: "týdny",
    UNIT_MONTHS: "měsíce",
    UNIT_YEARS: "roky",
}

NEXT_FROM_LABELS = {
    NEXT_FROM_PLANNED: "plánovaného termínu",
    NEXT_FROM_ACTUAL: "skutečného data provedení",
}

PERFORMER_KIND_THP = "thp"
PERFORMER_KIND_PERSON = "person"
PERFORMER_KIND_EXTERNAL = "external"
PERFORMER_KINDS = (
    PERFORMER_KIND_THP,
    PERFORMER_KIND_PERSON,
    PERFORMER_KIND_EXTERNAL,
)
PERFORMER_KIND_LABELS = {
    PERFORMER_KIND_THP: "THP",
    PERFORMER_KIND_PERSON: "Osoba",
    PERFORMER_KIND_EXTERNAL: "Externí / dodavatel",
}

TAB_TASKS_MEETINGS = "Úkoly a události"
TAB_PERIODIC = "Periodické činnosti"

ACTION_NEW = "Nová periodická činnost"
ACTION_EDIT = "Upravit"
ACTION_PERFORM = "Provedeno"
SHOW_INACTIVE_LABEL = "Zobrazit neaktivní"

DIALOG_TITLE_NEW = "Nová periodická činnost"
DIALOG_TITLE_EDIT = "Periodická činnost"
DIALOG_TITLE_PERFORM = "Provedení periodické činnosti"
TAB_ACTIVITY = "Činnost"
TAB_HISTORY = "Historie"

EMPTY_STATE_TEXT = "Nejsou evidovány žádné periodické činnosti odpovídající filtrům."
ITEM_NOT_FOUND_MESSAGE = "Periodická činnost nebyla nalezena."
TITLE_REQUIRED_MESSAGE = "Vyplňte název periodické činnosti."
PERFORMED_DATE_REQUIRED_MESSAGE = "Vyplňte datum provedení."
HISTORY_ATTACHMENTS_HINT = (
    "Vyberte provedení v historii pro zobrazení a správu příloh."
)
PERFORMANCE_ATTACHMENTS_HINT = (
    "Přílohy (protokol, zpráva, potvrzení, PDF, fotografie) lze přidat po uložení provedení."
)
HISTORY_ATTACHMENTS_LABEL = "Přílohy vybraného provedení"

COL_ID = 0
COL_TITLE = 1
COL_PLACE = 2
COL_RESPONSIBLE = 3
COL_NEXT_DUE = 4
COL_PERIOD = 5
COL_NOTIFY = 6
COL_ACTIVE = 7

COLUMN_HEADERS = [
    "ID",
    "Název",
    "Místo",
    "Odpovědná osoba",
    "Nejbližší termín",
    "Perioda",
    "Připomenout",
    "Aktivní",
]

HISTORY_HEADERS = [
    "Plánovaný termín",
    "Datum provedení",
    "Provedl",
    "Výsledek / poznámka",
]


def format_interval(every: int, unit: str) -> str:
    label = UNIT_LABELS.get(unit, unit)
    return f"{every} {label}"


def format_place(activity) -> str:
    kind = getattr(activity, "place_kind", PLACE_KIND_NONE)
    if kind == PLACE_KIND_WORKPLACE:
        name = (getattr(activity, "workplace_name", None) or "").strip()
        return name or PLACE_KIND_LABELS[PLACE_KIND_WORKPLACE]
    if kind == PLACE_KIND_OTHER:
        text = (getattr(activity, "place_text", None) or "").strip()
        return text or PLACE_KIND_LABELS[PLACE_KIND_OTHER]
    return PLACE_KIND_LABELS.get(kind, PLACE_KIND_LABELS[PLACE_KIND_NONE])


def format_notify(every: int, unit: str) -> str:
    if every <= 0:
        return "v den termínu"
    return f"{format_interval(every, unit)} před termínem"
