"""Konstanty evidence Státního dozoru (STATE-SUPERVISION-CORE-1)."""

from __future__ import annotations

MODULE_KEY = "state_supervision"
MODULE_NAME = "Státní dozor"
ENTITY_STATE_SUPERVISION = "state_supervision"

STATUS_ANNOUNCED = "announced"
STATUS_PREPARATION = "preparation"
STATUS_IN_PROGRESS = "in_progress"
STATUS_WAITING_PROTOCOL = "waiting_protocol"
STATUS_OBJECTIONS_PERIOD = "objections_period"
STATUS_MEASURES_IN_PROGRESS = "measures_in_progress"
STATUS_WAITING_AUTHORITY_CONFIRMATION = "waiting_authority_confirmation"
STATUS_CLOSED = "closed"
STATUS_CANCELLED = "cancelled"

DEFAULT_STATUS = STATUS_ANNOUNCED

STATE_SUPERVISION_STATUSES = frozenset(
    {
        STATUS_ANNOUNCED,
        STATUS_PREPARATION,
        STATUS_IN_PROGRESS,
        STATUS_WAITING_PROTOCOL,
        STATUS_OBJECTIONS_PERIOD,
        STATUS_MEASURES_IN_PROGRESS,
        STATUS_WAITING_AUTHORITY_CONFIRMATION,
        STATUS_CLOSED,
        STATUS_CANCELLED,
    }
)

STATE_SUPERVISION_STATUS_LABELS: dict[str, str] = {
    STATUS_ANNOUNCED: "Ohlášena",
    STATUS_PREPARATION: "V přípravě",
    STATUS_IN_PROGRESS: "Probíhá",
    STATUS_WAITING_PROTOCOL: "Čeká se na protokol",
    STATUS_OBJECTIONS_PERIOD: "Lhůta pro námitky",
    STATUS_MEASURES_IN_PROGRESS: "Plnění opatření",
    STATUS_WAITING_AUTHORITY_CONFIRMATION: "Čeká se na potvrzení orgánu",
    STATUS_CLOSED: "Uzavřena",
    STATUS_CANCELLED: "Zrušena",
}

STATE_SUPERVISION_STATUS_ORDER: tuple[str, ...] = (
    STATUS_ANNOUNCED,
    STATUS_PREPARATION,
    STATUS_IN_PROGRESS,
    STATUS_WAITING_PROTOCOL,
    STATUS_OBJECTIONS_PERIOD,
    STATUS_MEASURES_IN_PROGRESS,
    STATUS_WAITING_AUTHORITY_CONFIRMATION,
    STATUS_CLOSED,
    STATUS_CANCELLED,
)

STATE_SUPERVISION_STATUS_HINTS: dict[str, str] = {
    STATUS_ANNOUNCED: "Kontrola byla ohlášena.",
    STATUS_PREPARATION: "Připravují se podklady, účastníci a zastupování.",
    STATUS_IN_PROGRESS: "Kontrola právě probíhá.",
    STATUS_WAITING_PROTOCOL: "Kontrola proběhla a čeká se na doručení protokolu.",
    STATUS_OBJECTIONS_PERIOD: "Běží uložená lhůta pro podání námitek.",
    STATUS_MEASURES_IN_PROGRESS: "Probíhá plnění opatření uložených kontrolním orgánem.",
    STATUS_WAITING_AUTHORITY_CONFIRMATION: (
        "Podklady byly předány a čeká se na potvrzení kontrolního orgánu."
    ),
    STATUS_CLOSED: "Kontrola je uzavřena.",
    STATUS_CANCELLED: "Kontrola byla zrušena.",
}

TAB_STATE_SUPERVISION = MODULE_NAME

FILTER_ALL = "Všechny"
FILTER_MODE_ACTIVE = "Aktivní"
FILTER_MODE_CLOSED = "Uzavřené"
FILTER_MODES = (FILTER_ALL, FILTER_MODE_ACTIVE, FILTER_MODE_CLOSED)

EMPTY_STATE_NONE = "Zatím nejsou evidovány žádné kontroly státního dozoru."
EMPTY_STATE_FILTER = "Nastaveným filtrům neodpovídá žádná kontrola."
LOAD_ERROR_TEXT = "Přehled státního dozoru se nepodařilo načíst."
STATUS_CUBE_HINT = (
    "Barevná značka vyjadřuje stav kontroly. Podrobnosti zobrazíte najetím myši."
)
EMPTY_VALUE = "—"

COL_STATUS = 0
COL_AUTHORITY = 1
COL_WORKPLACE = 2
COL_STARTED = 3
COL_ENDED = 4
COL_RESULT = 5

COLUMN_HEADERS = [
    "Stav",
    "Kontrolní orgán",
    "Provoz / pracoviště",
    "Zahájení",
    "Ukončení",
    "Výsledek kontroly",
]

NOTIFICATION_METHOD_EMAIL = "email"
NOTIFICATION_METHOD_DATA_BOX = "data_box"
NOTIFICATION_METHOD_PHONE = "phone"
NOTIFICATION_METHOD_WRITTEN = "written"
NOTIFICATION_METHOD_IN_PERSON = "in_person"
NOTIFICATION_METHOD_OTHER = "other"

STATE_SUPERVISION_NOTIFICATION_METHODS = frozenset(
    {
        NOTIFICATION_METHOD_EMAIL,
        NOTIFICATION_METHOD_DATA_BOX,
        NOTIFICATION_METHOD_PHONE,
        NOTIFICATION_METHOD_WRITTEN,
        NOTIFICATION_METHOD_IN_PERSON,
        NOTIFICATION_METHOD_OTHER,
    }
)

STATE_SUPERVISION_NOTIFICATION_METHOD_LABELS: dict[str, str] = {
    NOTIFICATION_METHOD_EMAIL: "E-mail",
    NOTIFICATION_METHOD_DATA_BOX: "Datová schránka",
    NOTIFICATION_METHOD_PHONE: "Telefon",
    NOTIFICATION_METHOD_WRITTEN: "Písemně",
    NOTIFICATION_METHOD_IN_PERSON: "Osobně",
    NOTIFICATION_METHOD_OTHER: "Jinak",
}
