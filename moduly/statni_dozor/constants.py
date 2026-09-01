"""Konstanty evidence Státního dozoru (STATE-SUPERVISION-CORE-1)."""

from __future__ import annotations

from core.shared.constants import (
    ENTITY_STATE_SUPERVISION,
    FINDING_TYPE_NEDOSTATEK,
    FINDING_TYPE_PORUSENI_PREDPISU,
    FINDING_TYPE_PRILEZITOST,
    FINDING_TYPE_ZAVADA,
    FINDING_TYPE_ZJISTENI,
)

MODULE_KEY = "state_supervision"
MODULE_NAME = "Státní dozor"

STATE_SUPERVISION_FINDING_TYPES = frozenset(
    {
        FINDING_TYPE_PRILEZITOST,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_ZAVADA,
        FINDING_TYPE_PORUSENI_PREDPISU,
        FINDING_TYPE_ZJISTENI,
    }
)


def is_state_supervision_finding_type(finding_type: str) -> bool:
    """Povolená podmnožina druhů zjištění kontroly státního dozoru."""
    return finding_type in STATE_SUPERVISION_FINDING_TYPES


STATE_SUPERVISION_FINDING_TYPE_ORDER: tuple[str, ...] = (
    FINDING_TYPE_PRILEZITOST,
    FINDING_TYPE_NEDOSTATEK,
    FINDING_TYPE_ZAVADA,
    FINDING_TYPE_PORUSENI_PREDPISU,
    FINDING_TYPE_ZJISTENI,
)

# Popisky pouze pro UI Státního dozoru. Nesmí se míchat s FINDING_TYPE_LABELS
# (exporty auditů/prověrek). Zkratka PKZ zde označuje konkrétní Finding.
STATE_SUPERVISION_FINDING_TYPE_LABELS: dict[str, str] = {
    FINDING_TYPE_PRILEZITOST: "Příležitost ke zlepšení (PKZ)",
    FINDING_TYPE_NEDOSTATEK: "Nedostatek",
    FINDING_TYPE_ZAVADA: "Závada",
    FINDING_TYPE_PORUSENI_PREDPISU: "Porušení požadavku",
    FINDING_TYPE_ZJISTENI: "Jiné zjištění",
}


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
TAB_ATTACHMENTS = "Přílohy"

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

# Účastníci kontroly (STATE-SUPERVISION-PARTICIPANTS-CORE-3C0)
ENTITY_PARTICIPANT = "state_supervision_participant"
TABLE_PARTICIPANTS = "state_supervision_participants"

PARTICIPANT_ROLE_INSPECTOR = "inspector"
PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE = "employer_representative"
PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE = "authorized_representative"
PARTICIPANT_ROLE_MANAGEMENT = "management"
PARTICIPANT_ROLE_TRADE_UNION = "trade_union"
PARTICIPANT_ROLE_SPECIALIST = "specialist"
PARTICIPANT_ROLE_OTHER = "other"

PARTICIPANT_ROLES = frozenset(
    {
        PARTICIPANT_ROLE_INSPECTOR,
        PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE,
        PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE,
        PARTICIPANT_ROLE_MANAGEMENT,
        PARTICIPANT_ROLE_TRADE_UNION,
        PARTICIPANT_ROLE_SPECIALIST,
        PARTICIPANT_ROLE_OTHER,
    }
)

PARTICIPANT_ROLE_LABELS: dict[str, str] = {
    PARTICIPANT_ROLE_INSPECTOR: "Inspektor / kontrolor",
    PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE: "Zástupce zaměstnavatele",
    PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE: "Zmocněná osoba",
    PARTICIPANT_ROLE_MANAGEMENT: "Vedení",
    PARTICIPANT_ROLE_TRADE_UNION: "Odborová organizace",
    PARTICIPANT_ROLE_SPECIALIST: "Odborný pracovník",
    PARTICIPANT_ROLE_OTHER: "Jiný účastník",
}

PARTICIPANT_ROLE_ORDER: tuple[str, ...] = (
    PARTICIPANT_ROLE_INSPECTOR,
    PARTICIPANT_ROLE_EMPLOYER_REPRESENTATIVE,
    PARTICIPANT_ROLE_AUTHORIZED_REPRESENTATIVE,
    PARTICIPANT_ROLE_MANAGEMENT,
    PARTICIPANT_ROLE_TRADE_UNION,
    PARTICIPANT_ROLE_SPECIALIST,
    PARTICIPANT_ROLE_OTHER,
)

ATTENDANCE_ATTENDED = "attended"
ATTENDANCE_ABSENT = "absent"

PARTICIPANT_ATTENDANCE_STATUSES = frozenset(
    {
        ATTENDANCE_ATTENDED,
        ATTENDANCE_ABSENT,
    }
)

PARTICIPANT_ATTENDANCE_LABELS: dict[str, str] = {
    ATTENDANCE_ATTENDED: "Účastnil/a se",
    ATTENDANCE_ABSENT: "Neúčastnil/a se",
}

PARTICIPANT_SOURCE_PERSON = "person"
PARTICIPANT_SOURCE_THP_WORKER = "thp_worker"
PARTICIPANT_SOURCE_TYPES = frozenset(
    {
        PARTICIPANT_SOURCE_PERSON,
        PARTICIPANT_SOURCE_THP_WORKER,
    }
)

GROUP_PARTICIPANTS = "Účastníci kontroly"
EMPTY_PARTICIPANTS = "Zatím nejsou evidováni žádní účastníci kontroly."
DIALOG_PARTICIPANT_NEW = "Nový účastník kontroly"
DIALOG_PARTICIPANT_EDIT = "Účastník kontroly"
PARTICIPANT_NAME_REQUIRED_MESSAGE = "Není vyplněno jméno účastníka."
PARTICIPANT_IDENTITY_CONFLICT_MESSAGE = (
    "Nelze současně použít osobu z evidence a jiné ručně zadané jméno."
)

LABEL_PARTICIPANT_ROLE = "Role při kontrole"
LABEL_PARTICIPANT_CATALOG = "Osoba z evidence"
LABEL_PARTICIPANT_EXTERNAL_NAME = "Jméno externí osoby"
LABEL_PARTICIPANT_ORGANIZATION = "Organizace"
LABEL_PARTICIPANT_CONTACT = "Kontakt"
LABEL_PARTICIPANT_PLANNED = "Plánovaná účast"
LABEL_PARTICIPANT_ATTENDANCE = "Skutečná účast"
LABEL_PARTICIPANT_NOTE = "Poznámka"

ATTENDANCE_UNEVALUATED_LABEL = "Nevyhodnoceno"
PLANNED_YES_LABEL = "Ano"
PLANNED_NO_LABEL = "Ne"

COL_PARTICIPANT_ROLE = 0
COL_PARTICIPANT_NAME = 1
COL_PARTICIPANT_ORGANIZATION = 2
COL_PARTICIPANT_PLANNED = 3
COL_PARTICIPANT_ATTENDANCE = 4
COL_PARTICIPANT_CONTACT = 5
COL_PARTICIPANT_NOTE = 6

PARTICIPANT_COLUMN_HEADERS = [
    "Role",
    "Jméno",
    "Organizace",
    "Plánovaná účast",
    "Skutečná účast",
    "Kontakt",
    "Poznámka",
]

# Přílohy spisu (STATE-SUPERVISION-ATTACHMENTS-UI-4A3)
GROUP_ATTACHMENTS = "Přílohy spisu"
ATTACHMENTS_HINT = (
    "Zde lze uložit dokumenty k celému průběhu kontroly, například oznámení, "
    "plnou moc, předané podklady, protokol, námitky nebo doklady o splnění opatření."
)
EMPTY_ATTACHMENTS = "Zatím nejsou evidovány žádné přílohy spisu."
ACTION_ADD_ATTACHMENTS = "Přidat přílohy"
ACTION_OPEN = "Otevřít"
ACTION_RESTORE = "Vrátit"
ATTACHMENT_STATUS_SAVED = "Uloženo"
ATTACHMENT_STATUS_NEW = "Nová příloha"
ATTACHMENT_STATUS_REMOVE = "K odebrání"
ATTACHMENT_FILE_MISSING = "Soubor chybí"
ATTACHMENT_DUPLICATE_ONE = "Stejný soubor už je ve frontě příloh."
ATTACHMENT_DUPLICATE_MANY = "{count} souborů nebylo přidáno, protože už ve frontě jsou."
ATTACHMENT_FILE_FILTER = (
    "Běžné dokumenty (*.pdf *.odt *.doc *.docx *.xls *.xlsx "
    "*.png *.jpg *.jpeg *.webp *.txt *.zfo);;"
    "Všechny soubory (*.*)"
)
ATTACHMENT_OPEN_TITLE = "Přílohy spisu"
ATTACHMENT_OPEN_ERROR = "Soubor přílohy se nepodařilo otevřít."

COL_ATTACHMENT_NAME = 0
COL_ATTACHMENT_TYPE = 1
COL_ATTACHMENT_SIZE = 2
COL_ATTACHMENT_STATUS = 3

ATTACHMENT_COLUMN_HEADERS = [
    "Název souboru",
    "Typ",
    "Velikost",
    "Stav",
]

# Zjištění kontroly (STATE-SUPERVISION-FINDINGS-UI-5A3)
GROUP_COURSE_TIMELINE = "Průběh kontroly"
GROUP_FINDINGS = "Zjištění kontroly"
EMPTY_FINDINGS = "Zatím nejsou evidována žádná zjištění kontroly."
FINDING_TASK_LINKED = "Navázán"
FINDING_STORED_REMOVE_HINT = (
    "Uložené zjištění zůstává v historii. Lze jej upravit nebo označit jako vypořádané."
)
FINDING_DESCRIPTION_REQUIRED_MESSAGE = "Není vyplněn popis zjištění."
DIALOG_FINDING_NEW = "Nové zjištění"
DIALOG_FINDING_EDIT = "Zjištění kontroly"

LABEL_FINDING_TYPE = "Druh zjištění"
LABEL_FINDING_DESCRIPTION = "Popis zjištění"
LABEL_FINDING_PLACE = "Místo / oblast"
LABEL_FINDING_STATUS = "Stav"
LABEL_FINDING_PERSON = "Odpovědná osoba"
LABEL_FINDING_DUE = "Termín"
LABEL_FINDING_RECOMMENDED = "Doporučené opatření"
LABEL_FINDING_RESOLUTION = "Poznámka k vypořádání"
LABEL_FINDING_RESOLVED_AT = "Vypořádáno dne"

COL_FINDING_TYPE = 0
COL_FINDING_DESCRIPTION = 1
COL_FINDING_PLACE = 2
COL_FINDING_STATUS = 3
COL_FINDING_PERSON = 4
COL_FINDING_DUE = 5
COL_FINDING_TASK = 6

FINDING_COLUMN_HEADERS = [
    "Druh",
    "Popis",
    "Místo / oblast",
    "Stav",
    "Odpovědná osoba",
    "Termín",
    "Úkol",
]
