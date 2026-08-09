"""Konstanty modulu Smlouvy OZO."""

MODULE_KEY = "smlouvy_ozo"
MODULE_NAME = "Smlouvy OZO"
MODULE_DESCRIPTION = "Evidence smluv OZO se zaměstnavateli / objednateli."

ENTITY_OZO_CONTRACT = "ozo_contract"
ENTITY_OZO_PERSON = "ozo_person"

ACTION_NEW = "Nová smlouva"
ACTION_EDIT = "Upravit"
ACTION_ACTIVATE = "Aktivovat"
ACTION_DEACTIVATE = "Deaktivovat"
ACTION_OZO_PERSON = "Odborně způsobilá osoba"
ACTION_CHRONOLOGICAL_LIST = "Chronologický seznam smluv"

DIALOG_TITLE_NEW = "Nová smlouva OZO"
DIALOG_TITLE_EDIT = "Smlouva OZO"
DIALOG_TITLE_OZO_PERSON = "Odborně způsobilá osoba"
DIALOG_TITLE_CHRONOLOGICAL_LIST = "Chronologický seznam smluv"

SHOW_INACTIVE_LABEL = "Zobrazit neaktivní"
YEAR_FILTER_ALL = "Vše"
EMPTY_STATE_TEXT = "Nejsou evidovány žádné smlouvy OZO."
EMPTY_STATE_YEAR_TEXT = "Pro zvolený rok nejsou evidovány žádné smluvní vztahy."
ITEM_NOT_FOUND_MESSAGE = "Smlouva OZO nebyla nalezena."
EMPLOYER_NAME_REQUIRED_MESSAGE = "Vyplňte název zaměstnavatele / objednatele."
VALID_FROM_REQUIRED_MESSAGE = "Vyplňte datum platnosti od."
VALID_TO_REQUIRED_MESSAGE = "U smlouvy na dobu určitou vyplňte platnost do."
YEAR_REQUIRED_FOR_LIST_MESSAGE = "Pro chronologický seznam smluv vyberte kalendářní rok."
OZO_PERSON_MISSING_MESSAGE = (
    "Pro výstup chronologického seznamu smluv doplňte údaje OZO:\n\n{items}"
)

DOCUMENT_LIST_TITLE = "Chronologický seznam smluvních vztahů"
DOCUMENT_LIST_LEGAL = (
    "Podle § 10 odst. 4 písm. a) zákona č. 309/2006 Sb."
)

UNIT_DAYS = "days"
UNIT_WEEKS = "weeks"
UNIT_MONTHS = "months"

NOTIFY_UNITS = (
    UNIT_DAYS,
    UNIT_WEEKS,
    UNIT_MONTHS,
)

UNIT_LABELS = {
    UNIT_DAYS: "dny",
    UNIT_WEEKS: "týdny",
    UNIT_MONTHS: "měsíce",
}

DEFAULT_NOTIFY_BEFORE_VALUE = 30
DEFAULT_NOTIFY_BEFORE_UNIT = UNIT_DAYS

STATUS_INACTIVE = "inactive"
STATUS_ACTIVE = "active"
STATUS_ENDING = "ending"
STATUS_EXPIRED = "expired"

STATUS_LABELS = {
    STATUS_INACTIVE: "Neaktivní",
    STATUS_ACTIVE: "Aktivní",
    STATUS_ENDING: "Končí",
    STATUS_EXPIRED: "Po platnosti",
}

COL_ID = 0
COL_EMPLOYER = 1
COL_ICO = 2
COL_NUMBER = 3
COL_VALID_FROM = 4
COL_VALID_TO = 5
COL_STATUS = 6

COLUMN_HEADERS = [
    "ID",
    "Zaměstnavatel",
    "IČO",
    "Číslo smlouvy",
    "Platnost od",
    "Platnost do",
    "Stav",
]


def format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return str(value)


def format_valid_to(*, indefinite: bool, valid_to) -> str:
    if indefinite:
        return "neurčitá"
    return format_date(valid_to)


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def format_ozo_display_name(
    title_before: str = "",
    first_name: str = "",
    last_name: str = "",
    title_after: str = "",
) -> str:
    """Složí zobrazované jméno OZO včetně titulů bez zdvojených mezer/čárek."""
    before = (title_before or "").strip()
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    after = (title_after or "").strip()

    base = " ".join(part for part in (before, first, last) if part)
    if not after:
        return base
    if after.startswith(","):
        return f"{base}{after}" if base else after.lstrip(", ").strip()
    if not base:
        return after
    return f"{base}, {after}"
