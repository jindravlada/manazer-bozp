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

STATE_SUPERVISION_NOTIFICATION_METHOD_ORDER: tuple[str, ...] = (
    NOTIFICATION_METHOD_EMAIL,
    NOTIFICATION_METHOD_DATA_BOX,
    NOTIFICATION_METHOD_PHONE,
    NOTIFICATION_METHOD_WRITTEN,
    NOTIFICATION_METHOD_IN_PERSON,
    NOTIFICATION_METHOD_OTHER,
)

# Popisky v editoru (CORE-1 ukládá kódy; „Telefonicky“ je jen UI).
STATE_SUPERVISION_NOTIFICATION_METHOD_EDITOR_LABELS: dict[str, str] = {
    **STATE_SUPERVISION_NOTIFICATION_METHOD_LABELS,
    NOTIFICATION_METHOD_PHONE: "Telefonicky",
}

NOTIFICATION_METHOD_EMPTY_LABEL = "nevyplněno"

ACTION_NEW = "Nový státní dozor"
ACTION_EDIT = "Upravit"
ACTION_SAVE_AND_CLOSE = "Uložit a zavřít"

DIALOG_TITLE_NEW = "Nový státní dozor"
DIALOG_TITLE_EDIT = "Státní dozor"

TAB_ANNOUNCEMENT = "Ohlášení a zahájení"
TAB_SUBJECT_PREPARATION = "Předmět a příprava"
TAB_COURSE = "Průběh kontroly"
TAB_CONCLUSION = "Závěr a opatření"

AUTHORITY_SUGGESTIONS: tuple[str, ...] = (
    "Obvodní báňský úřad (OBÚ)",
    "Oblastní inspektorát práce (OIP)",
    "Krajská hygienická stanice (KHS)",
    "Hasičský záchranný sbor (HZS)",
    "Drážní úřad (DÚ)",
)

AUTHORITY_REQUIRED_MESSAGE = "Není vyplněn kontrolní orgán."
ENDED_BEFORE_STARTED_MESSAGE = (
    "Datum a čas ukončení nesmí být dříve než datum a čas zahájení."
)
CLOSED_AT_REQUIRED_MESSAGE = (
    "Není vyplněno datum a čas administrativního uzavření."
)
CLOSED_BEFORE_ENDED_MESSAGE = (
    "Datum a čas administrativního uzavření nesmí být dříve "
    "než skutečné ukončení kontroly."
)
OBJECTIONS_BEFORE_PROTOCOL_MESSAGE = (
    "Datum podání námitek nesmí být dříve než datum doručení protokolu."
)
SAVE_ERROR_MESSAGE = "Kontrolu státního dozoru se nepodařilo uložit."
ITEM_NOT_FOUND_MESSAGE = "Kontrola státního dozoru už není k dispozici."

GROUP_NOTIFICATION = "Ohlášení kontroly"
GROUP_PLANNED_START = "Plánované zahájení"
GROUP_ACTUAL_COURSE = "Skutečný průběh"
GROUP_INFORMING = "Informování"
GROUP_REPRESENTATION = "Zastupování"
GROUP_SUBJECT = "Předmět kontroly"
GROUP_INITIAL_INFORMATION = "Prvotní informace od inspektora"
GROUP_PREPARATION = "Příprava kontroly"
GROUP_RESULT = "Výsledek kontroly"
GROUP_PROTOCOL = "Protokol"
GROUP_OBJECTIONS = "Námitky"
GROUP_COMPLETION_CLOSE = "Doložení splnění a uzavření"

RESULT_SUGGESTIONS: tuple[str, ...] = (
    "Bez zjištěných nedostatků",
    "Zjištěny nedostatky",
    "Uložena opatření",
    "Zahájeno navazující řízení",
    "Jiný výsledek",
)

LABEL_AUTHORITY = "Kontrolní orgán"
LABEL_AUTHORITY_ICO = "IČ"
LABEL_AUTHORITY_ADDRESS = "Adresa kontrolního orgánu"
LABEL_WORKPLACE = "Provoz / pracoviště"
LABEL_STATUS = "Stav kontroly"
LABEL_NOTIFICATION_METHOD = "Způsob ohlášení"
LABEL_ANNOUNCED_AT = "Datum a čas ohlášení"
LABEL_FILE_NUMBER = "Číslo jednací"
LABEL_NOTIFICATION_NOTE = "Poznámka k ohlášení"
LABEL_PLANNED_START_AT = "Plánované datum a čas zahájení"
LABEL_PLANNED_START_PLACE = "Místo zahájení"
LABEL_PLANNED_CONTROL_PLACE = "Místo provedení kontroly"
LABEL_STARTED_AT = "Skutečné datum a čas zahájení"
LABEL_ENDED_AT = "Skutečné datum a čas ukončení"
LABEL_TRADE_UNION_NOTIFIED_AT = "Odborová organizace informována"
LABEL_MANAGEMENT_NOTIFIED_AT = "Vedení informováno"
LABEL_POWER_OF_ATTORNEY = "Je vyžadována plná moc"
LABEL_POWER_OF_ATTORNEY_NOTE = "Poznámka k plné moci"
LABEL_SUBJECT = "Předmět a tematika kontroly"
LABEL_INITIAL_INFORMATION = "Prvotní informace od inspektora"
LABEL_PREPARATION_NOTE = "Co je potřeba zajistit a připravit"
LABEL_RESULT = "Výsledek kontroly"
LABEL_FINAL_SUMMARY = "Závěrečné shrnutí"
LABEL_PROTOCOL_NUMBER = "Číslo protokolu"
LABEL_PROTOCOL_RECEIVED_AT = "Protokol doručen dne a v kolik"
LABEL_OBJECTIONS_DUE_AT = "Lhůta pro podání námitek"
LABEL_OBJECTIONS_SUBMITTED_AT = "Námitky podány dne a v kolik"
LABEL_OBJECTIONS_NOTE = "Poznámka k námitkám"
LABEL_COMPLETION_EVIDENCE_SENT_AT = "Doklady o splnění odeslány dne a v kolik"
LABEL_AUTHORITY_CONFIRMATION_AT = "Potvrzení kontrolního orgánu přijato dne a v kolik"
LABEL_CLOSED_AT = "Kontrola administrativně uzavřena dne a v kolik"

TOOLTIP_SUBJECT = (
    "Důvod kontroly, tematika, rozsah a kontrolované činnosti nebo oblasti."
)
TOOLTIP_INITIAL_INFORMATION = (
    "Co inspektor předběžně sdělil, na co se zaměří a co bude chtít ověřit."
)
TOOLTIP_PREPARATION_NOTE = (
    "Požadované materiály, dokumenty, organizační zajištění a potřebná součinnost."
)

# Požadované doklady (STATE-SUPERVISION-DOCUMENTS-CORE-2C0 / UI-2C1)
ENTITY_REQUIRED_DOCUMENT = "state_supervision_required_document"
TABLE_REQUIRED_DOCUMENTS = "state_supervision_required_documents"

GROUP_REQUIRED_DOCUMENTS = "Požadované doklady a podklady"
EMPTY_DOCUMENTS = "Zatím nejsou evidovány žádné požadované doklady."
DIALOG_DOCUMENT_NEW = "Nový požadovaný doklad"
DIALOG_DOCUMENT_EDIT = "Požadovaný doklad"
DOCUMENT_TITLE_REQUIRED_MESSAGE = "Není vyplněn název dokladu / podkladu."

LABEL_DOCUMENT_TITLE = "Doklad / podklad"
LABEL_DOCUMENT_RESPONSIBLE = "Odpovědná osoba"
LABEL_DOCUMENT_DUE = "Termín"
LABEL_DOCUMENT_PREPARED = "Připraveno dne"
LABEL_DOCUMENT_SUBMITTED = "Předáno dne"
LABEL_DOCUMENT_NOTE = "Poznámka"

COL_DOCUMENT_TITLE = 0
COL_DOCUMENT_RESPONSIBLE = 1
COL_DOCUMENT_DUE = 2
COL_DOCUMENT_PREPARED = 3
COL_DOCUMENT_SUBMITTED = 4
COL_DOCUMENT_NOTE = 5

DOCUMENT_COLUMN_HEADERS = [
    "Doklad / podklad",
    "Odpovědná osoba",
    "Termín",
    "Připraveno",
    "Předáno",
    "Poznámka",
]

ACTION_ADD = "Přidat"
ACTION_REMOVE = "Odebrat"
ACTION_MOVE_UP = "Nahoru"
ACTION_MOVE_DOWN = "Dolů"

RESPONSIBLE_SOURCE_PERSON = "person"
RESPONSIBLE_SOURCE_THP_WORKER = "thp_worker"
RESPONSIBLE_SOURCE_TYPES = frozenset(
    {
        RESPONSIBLE_SOURCE_PERSON,
        RESPONSIBLE_SOURCE_THP_WORKER,
    }
)

# Průběh kontroly (STATE-SUPERVISION-TIMELINE-CORE-3A0 / UI-3A1)
ENTITY_TIMELINE_ITEM = "state_supervision_timeline_item"
TABLE_TIMELINE_ITEMS = "state_supervision_timeline_items"

EMPTY_TIMELINE = "Zatím nejsou zaznamenány žádné údaje z průběhu kontroly."
TIMELINE_HINT = (
    "Zaznamenávejte jednotlivé úkony a poznámky z průběhu kontroly. "
    "Změny se uloží až hlavním tlačítkem Uložit."
)
DIALOG_TIMELINE_NEW = "Nový záznam průběhu"
DIALOG_TIMELINE_EDIT = "Záznam průběhu"
TIMELINE_TITLE_REQUIRED_MESSAGE = "Není vyplněn název záznamu."

LABEL_TIMELINE_OCCURRED_AT = "Datum a čas"
LABEL_TIMELINE_TITLE = "Název záznamu"
LABEL_TIMELINE_PLACE = "Místo"
LABEL_TIMELINE_NOTES = "Zápis z průběhu"

COL_TIMELINE_OCCURRED = 0
COL_TIMELINE_TITLE = 1
COL_TIMELINE_PLACE = 2
COL_TIMELINE_NOTES = 3

TIMELINE_COLUMN_HEADERS = [
    "Datum a čas",
    "Název záznamu",
    "Místo",
    "Zápis z průběhu",
]
