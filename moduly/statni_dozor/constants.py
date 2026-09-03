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
    "Barevná značka vyjadřuje stav kontroly. Červená upozorňuje na nevyřešený "
    "problém nebo prošlou evidovanou lhůtu. Podrobnosti zobrazíte najetím myši."
)
ATTENTION_TOOLTIP_STATUS_PREFIX = "Stav:"
ATTENTION_TOOLTIP_ALERT_HEADING = "Upozornění:"
ATTENTION_EVALUATION_FAILED_MESSAGE = "Stav upozornění se nepodařilo vyhodnotit."
ATTENTION_REASON_OVERDUE_DOCUMENTS = "overdue_documents"
ATTENTION_REASON_OVERDUE_FINDINGS = "overdue_findings"
ATTENTION_REASON_OVERDUE_TASKS = "overdue_tasks"
ATTENTION_REASON_MISSING_TASKS = "missing_tasks"
ATTENTION_REASON_OVERDUE_OBJECTIONS = "overdue_objections"
ATTENTION_REASON_OVERDUE_PLANNED_START = "overdue_planned_start"
ATTENTION_REASON_LABELS: dict[str, str] = {
    ATTENTION_REASON_OVERDUE_DOCUMENTS: "požadované doklady po termínu",
    ATTENTION_REASON_OVERDUE_FINDINGS: "zjištění po termínu",
    ATTENTION_REASON_OVERDUE_TASKS: "navazující úkoly po termínu",
    ATTENTION_REASON_MISSING_TASKS: "chybějící navázané úkoly",
    ATTENTION_REASON_OVERDUE_OBJECTIONS: "uplynula lhůta pro podání námitek",
    ATTENTION_REASON_OVERDUE_PLANNED_START: "uplynul plánovaný termín zahájení",
}
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
WORKSPACE_REFRESH_FAILED_MESSAGE = (
    "Data byla uložena, ale pracovní plochu se nepodařilo obnovit. "
    "Obnovte ji prosím ručně."
)
ITEM_NOT_FOUND_MESSAGE = "Kontrola státního dozoru už není k dispozici."
DOCUMENT_NOT_IN_ACTIVE_LIST_MESSAGE = (
    "Požadovaný doklad již není v aktivním seznamu."
)
FINDING_NO_LONGER_AVAILABLE_MESSAGE = "Zjištění již není k dispozici."

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
LABEL_AUTHORITY_ADDRESS = "Adresa"
LABEL_AUTHORITY_OFFICE = "Příslušné pracoviště"
LABEL_WORKPLACE = "Provoz / pracoviště"
LABEL_STATUS = "Stav kontroly"
LABEL_NOTIFICATION_METHOD = "Způsob ohlášení"
LABEL_ANNOUNCED_AT = "Datum a čas ohlášení"
LABEL_FILE_NUMBER = "Číslo jednací"
LABEL_NOTIFICATION_NOTE = "Poznámka k ohlášení"
LABEL_PLANNED_START_AT = "Plánované datum a čas zahájení"
LABEL_PLANNED_START_PLACE = "Místo setkání"
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
ACTION_CREATE_TASK = "Vytvořit úkol"
ACTION_OPEN_TASK = "Otevřít úkol"
FINDING_TASK_SAVE_FIRST_TOOLTIP = "Nejprve uložte kontrolu a zjištění."
FINDING_TASK_DIRTY_TOOLTIP = (
    "Před vytvořením úkolu nejprve uložte všechny změny kontroly."
)
FINDING_TASK_HINT_UNSAVED = "Úkol lze vytvořit po uložení zjištění."
FINDING_TASK_HINT_DIRTY = "Před vytvořením úkolu nejprve uložte změny kontroly."
FINDING_TASK_HINT_LINKED = "Ke zjištění je již navázán úkol."
FINDING_TASK_MISSING_LABEL = "Úkol nebyl nalezen"
FINDING_TASK_MISSING_OPEN_MESSAGE = "Navázaný úkol nebyl nalezen."
FINDING_TASK_RELOAD_FAILED_MESSAGE = (
    "Úkol byl vytvořen, ale nepodařilo se obnovit obrazovku. "
    "Zavřete editor a otevřete kontrolu znovu."
)
FINDING_TASK_NOT_FOUND_MESSAGE = "Zjištění nebylo nalezeno."
FINDING_TASK_WRONG_ENTITY_MESSAGE = (
    "Úkol ze zjištění lze vytvořit jen pro kontrolu státního dozoru."
)
FINDING_TASK_ALREADY_LINKED_MESSAGE = "Zjištění už má navázaný úkol."
FINDING_TASK_MISSING_TASK_MESSAGE = "Zjištění odkazuje na neexistující úkol."
FINDING_SOURCE_MISSING_MESSAGE = "Zjištění se nepodařilo otevřít."
FINDING_PARENT_MISSING_MESSAGE = "Kontrola státního dozoru už není k dispozici."
FINDING_STORED_REMOVE_HINT = (
    "Uložené zjištění zůstává v historii. Lze jej upravit nebo označit jako vypořádané."
)
FINDING_DESCRIPTION_REQUIRED_MESSAGE = "Není vyplněn popis zjištění."
ACTION_CONFIRM_CLOSE_SUPERVISION = "Uzavřít kontrolu"
CLOSURE_WARNING_INTRO = "Kontrola dosud obsahuje:"
CLOSURE_WARNING_OPEN_FINDINGS = "otevřená nebo rozpracovaná zjištění"
CLOSURE_WARNING_ACTIVE_TASKS = "neukončené navazující úkoly"
CLOSURE_WARNING_MISSING_TASKS = "chybějící navázané úkoly"
CLOSURE_WARNING_FOOTER = (
    "Kontrolu lze uzavřít, ale tyto položky zůstanou nadále evidované. "
    "Chcete kontrolu přesto uzavřít?"
)
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

# Katalog kontrolních orgánů (STATE-SUPERVISION-AUTHORITY-CATALOG-CORE-8A0)
AUTHORITY_ORIGIN_BUNDLED = "bundled"
AUTHORITY_ORIGIN_WEB = "web"
AUTHORITY_ORIGIN_MANUAL = "manual"
AUTHORITY_ORIGINS: frozenset[str] = frozenset(
    {
        AUTHORITY_ORIGIN_BUNDLED,
        AUTHORITY_ORIGIN_WEB,
        AUTHORITY_ORIGIN_MANUAL,
    }
)
AUTHORITY_IMPORT_ORIGINS: frozenset[str] = frozenset(
    {AUTHORITY_ORIGIN_BUNDLED, AUTHORITY_ORIGIN_WEB}
)

OFFICE_KIND_HEADQUARTERS = "headquarters"
OFFICE_KIND_REGIONAL = "regional"
OFFICE_KIND_TERRITORIAL = "territorial"
OFFICE_KIND_OTHER = "other"
OFFICE_KINDS: frozenset[str] = frozenset(
    {
        OFFICE_KIND_HEADQUARTERS,
        OFFICE_KIND_REGIONAL,
        OFFICE_KIND_TERRITORIAL,
        OFFICE_KIND_OTHER,
    }
)

AUTHORITY_CODE_REQUIRED_MESSAGE = "Není vyplněn kód kontrolního orgánu."
AUTHORITY_NAME_REQUIRED_MESSAGE = "Není vyplněn název kontrolního orgánu."
AUTHORITY_CODE_DUPLICATE_MESSAGE = "Kód kontrolního orgánu už existuje."
AUTHORITY_EXTERNAL_KEY_DUPLICATE_MESSAGE = (
    "Technický klíč kontrolního orgánu už existuje."
)
AUTHORITY_ORIGIN_INVALID_MESSAGE = "Neplatný původ záznamu kontrolního orgánu."
AUTHORITY_DISPLAY_ORDER_INVALID_MESSAGE = (
    "Pořadí zobrazení kontrolního orgánu nesmí být záporné."
)
AUTHORITY_NOT_FOUND_MESSAGE = "Kontrolní orgán už není k dispozici."
AUTHORITY_HAS_ACTIVE_OFFICES_MESSAGE = (
    "Kontrolní orgán má aktivní pracoviště. Nejprve je deaktivujte."
)

OFFICE_NAME_REQUIRED_MESSAGE = "Není vyplněn název příslušného pracoviště."
OFFICE_AUTHORITY_REQUIRED_MESSAGE = "Není vyplněn kontrolní orgán pracoviště."
OFFICE_KIND_INVALID_MESSAGE = "Neplatný druh pracoviště kontrolního orgánu."
OFFICE_ORIGIN_INVALID_MESSAGE = (
    "Neplatný původ záznamu pracoviště kontrolního orgánu."
)
OFFICE_EXTERNAL_KEY_DUPLICATE_MESSAGE = (
    "Technický klíč pracoviště kontrolního orgánu už existuje."
)
OFFICE_DISPLAY_ORDER_INVALID_MESSAGE = (
    "Pořadí zobrazení pracoviště nesmí být záporné."
)
OFFICE_NOT_FOUND_MESSAGE = "Příslušné pracoviště už není k dispozici."
OFFICE_ACTIVE_UNDER_INACTIVE_AUTHORITY_MESSAGE = (
    "Aktivní příslušné pracoviště nelze evidovat u neaktivního kontrolního orgánu."
)

AUTHORITY_ORIGIN_LABELS: dict[str, str] = {
    AUTHORITY_ORIGIN_BUNDLED: "Výchozí",
    AUTHORITY_ORIGIN_WEB: "Z webu",
    AUTHORITY_ORIGIN_MANUAL: "Ručně",
}
OFFICE_KIND_USER_LABELS: dict[str, str] = {
    OFFICE_KIND_HEADQUARTERS: "Centrální",
    OFFICE_KIND_REGIONAL: "Regionální",
    OFFICE_KIND_TERRITORIAL: "Územní",
    OFFICE_KIND_OTHER: "Jiné",
}
CATALOG_ROW_KIND_AUTHORITY = "Kontrolní orgán"
CATALOG_ROW_KIND_OFFICE = "Příslušné pracoviště"
OFFICE_CATALOG_TOOLTIP = (
    "Konkrétní oblastní, obvodní, krajské nebo územní pracoviště "
    "kontrolního orgánu, které kontrolu ohlásilo nebo provádí."
)
CATALOG_MANUAL_EDIT_HINT = (
    "Ručně upravené údaje nebudou při webové kontrole automaticky přepsány."
)
CATALOG_SHOW_INACTIVE_LABEL = "Zobrazit neaktivní"
CATALOG_NEW_AUTHORITY_LABEL = "Nový kontrolní orgán"
CATALOG_NEW_OFFICE_LABEL = "Nové pracoviště"
CATALOG_EMPTY_TEXT = "Zatím nejsou evidovány žádné kontrolní orgány."
CATALOG_FILTER_EMPTY_TEXT = (
    "Zadanému hledání neodpovídá žádný kontrolní orgán ani příslušné pracoviště."
)
CATALOG_LOAD_ERROR_TEXT = "Katalog kontrolních orgánů se nepodařilo načíst."
CATALOG_UNAVAILABLE_EDITOR_TEXT = (
    "Katalog kontrolních orgánů není dostupný. "
    "Orgán i pracoviště lze zadat ručně."
)
CATALOG_REFRESH_AFTER_SAVE_MESSAGE = (
    "Záznam je uložený, ale přehled se nepodařilo obnovit."
)
CATALOG_DEACTIVATE_AUTHORITY_TITLE = "Deaktivovat kontrolní orgán"
CATALOG_DEACTIVATE_OFFICE_TITLE = "Deaktivovat příslušné pracoviště"
CATALOG_CODE_PLACEHOLDER = "Při uložení se odvodí z názvu."
CATALOG_HAS_ACTIVE_OFFICES_TOOLTIP = (
    "Nejprve deaktivujte příslušná pracoviště."
)

# Seed katalogu (STATE-SUPERVISION-AUTHORITY-CATALOG-SEED-8A1)
AUTHORITY_CATALOG_SEED_RELATIVE_PATH = "ciselniky/statni_dozor/kontrolni_organy.json"
AUTHORITY_CATALOG_SEED_SCHEMA_VERSION = 1
AUTHORITY_CATALOG_SEED_STARTUP_MESSAGE = (
    "Výchozí katalog kontrolních orgánů se nepodařilo načíst. "
    "Aplikaci nelze spustit."
)
AUTHORITY_CATALOG_SEED_SCHEMA_INVALID_MESSAGE = (
    "Výchozí katalog kontrolních orgánů má neznámou verzi schématu."
)
AUTHORITY_CATALOG_SEED_KEY_REQUIRED_MESSAGE = (
    "Výchozí katalog kontrolních orgánů musí mít vyplněný technický klíč."
)
AUTHORITY_CATALOG_SEED_DUPLICATE_KEY_MESSAGE = (
    "Výchozí katalog kontrolních orgánů obsahuje duplicitní technický klíč."
)
AUTHORITY_CATALOG_SEED_DUPLICATE_CODE_MESSAGE = (
    "Výchozí katalog kontrolních orgánů obsahuje duplicitní kód orgánu."
)
AUTHORITY_CATALOG_SEED_ICO_FORBIDDEN_MESSAGE = (
    "Výchozí katalog kontrolních orgánů nesmí obsahovat IČ."
)
AUTHORITY_CATALOG_SEED_URL_INVALID_MESSAGE = (
    "Výchozí katalog kontrolních orgánů obsahuje URL s nepovoleným schématem."
)
AUTHORITY_CATALOG_SEED_ADDRESS_REQUIRED_MESSAGE = (
    "Ve výchozím katalogu musí mít pracoviště vyplněnou adresu."
)
AUTHORITY_CATALOG_SEED_COLLISION_MESSAGE = (
    "Výchozí katalog kontrolních orgánů nelze importovat, "
    "protože technický klíč koliduje s existujícím záznamem."
)

# Webové adaptéry kontrolních orgánů (STATE-SUPERVISION-AUTHORITY-WEB-DU-8D0)
DU_AUTHORITY_CODE = "du"
DU_OFFICES_SOURCE_URL = "https://du.gov.cz/kontakty/"
DU_OFFICE_EXTERNAL_KEYS: tuple[str, ...] = ("du:praha", "du:plzen", "du:olomouc")
WEB_ADAPTER_ERROR_NETWORK = "network"
WEB_ADAPTER_ERROR_TIMEOUT = "timeout"
WEB_ADAPTER_ERROR_HTTP = "http"
WEB_ADAPTER_ERROR_INVALID_URL = "invalid_url"
WEB_ADAPTER_ERROR_TOO_LARGE = "too_large"
WEB_ADAPTER_ERROR_UNSUPPORTED_CONTENT = "unsupported_content"
WEB_ADAPTER_ERROR_UNREADABLE_HTML = "unreadable_html"
WEB_ADAPTER_ERROR_INCOMPLETE = "incomplete"
WEB_ADAPTER_ERROR_DUPLICATE_KEY = "duplicate_key"
WEB_ADAPTER_NETWORK_MESSAGE = "Stránku kontrolního orgánu se nepodařilo načíst."
WEB_ADAPTER_TIMEOUT_MESSAGE = "Načtení stránky kontrolního orgánu vypršelo."
WEB_ADAPTER_HTTP_MESSAGE = "Oficiální stránka kontrolního orgánu vrátila chybovou odpověď."
WEB_ADAPTER_INVALID_URL_MESSAGE = "Adresa oficiální stránky kontrolního orgánu není povolená."
WEB_ADAPTER_TOO_LARGE_MESSAGE = "Odpověď oficiální stránky kontrolního orgánu je příliš velká."
WEB_ADAPTER_UNSUPPORTED_CONTENT_MESSAGE = (
    "Oficiální stránka kontrolního orgánu nevrátila očekávaný HTML obsah."
)
WEB_ADAPTER_UNREADABLE_HTML_MESSAGE = (
    "Strukturu oficiální stránky kontrolního orgánu nelze bezpečně přečíst."
)
WEB_ADAPTER_INCOMPLETE_MESSAGE = (
    "Oficiální stránka kontrolního orgánu neobsahuje kompletní seznam pracovišť."
)
WEB_ADAPTER_DUPLICATE_KEY_MESSAGE = (
    "Oficiální stránka kontrolního orgánu obsahuje duplicitní pracoviště."
)
WEB_ADAPTER_HTTP_TIMEOUT_SECONDS = 20
WEB_ADAPTER_MAX_RESPONSE_BYTES = 1_048_576

# Porovnání webu s katalogem (STATE-SUPERVISION-AUTHORITY-WEB-DIFF-8D1)
WEB_DIFF_STATUS_UNCHANGED = "unchanged"
WEB_DIFF_STATUS_NEW = "new"
WEB_DIFF_STATUS_CHANGED = "changed"
WEB_DIFF_STATUS_MISSING_REMOTE = "missing_remote"
WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE = "protected_missing_remote"
WEB_DIFF_STATUS_INACTIVE_PRESENT = "inactive_present"
WEB_DIFF_STATUS_PROTECTED = "protected"
WEB_DIFF_STATUS_POSSIBLE_DUPLICATE = "possible_duplicate"
WEB_DIFF_STATUS_IDENTITY_CONFLICT = "identity_conflict"
WEB_DIFF_STATUSES: tuple[str, ...] = (
    WEB_DIFF_STATUS_UNCHANGED,
    WEB_DIFF_STATUS_NEW,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_MISSING_REMOTE,
    WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
    WEB_DIFF_STATUS_INACTIVE_PRESENT,
    WEB_DIFF_STATUS_PROTECTED,
    WEB_DIFF_STATUS_POSSIBLE_DUPLICATE,
    WEB_DIFF_STATUS_IDENTITY_CONFLICT,
)
WEB_DIFF_ACTION_NONE = "none"
WEB_DIFF_ACTION_CREATE = "create"
WEB_DIFF_ACTION_UPDATE = "update"
WEB_DIFF_ACTION_DEACTIVATE = "deactivate"
WEB_DIFF_ACTION_REACTIVATE = "reactivate"
WEB_DIFF_ACTION_REVIEW = "review"
WEB_DIFF_COMPARED_FIELDS: tuple[str, ...] = (
    "name",
    "address",
    "phone",
    "email",
    "website",
    "territorial_scope",
    "office_kind",
    "source_url",
)
WEB_DIFF_ERROR_INCOMPLETE = "incomplete_result"
WEB_DIFF_ERROR_MISSING_KEY = "missing_external_key"
WEB_DIFF_ERROR_DUPLICATE_REMOTE = "duplicate_remote_key"
WEB_DIFF_ERROR_DUPLICATE_LOCAL = "duplicate_local_key"
WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND = "authority_not_found"
WEB_DIFF_INCOMPLETE_MESSAGE = (
    "Výsledek webového adapteru není úplný a nelze podle něj navrhovat změny katalogu."
)
WEB_DIFF_MISSING_KEY_MESSAGE = (
    "Webový záznam pracoviště musí mít vyplněný technický klíč."
)
WEB_DIFF_DUPLICATE_REMOTE_MESSAGE = (
    "Webový výsledek obsahuje duplicitní technický klíč pracoviště."
)
WEB_DIFF_DUPLICATE_LOCAL_MESSAGE = (
    "Místní katalog obsahuje duplicitní technický klíč pracoviště."
)
WEB_DIFF_AUTHORITY_NOT_FOUND_MESSAGE = (
    "Kontrolní orgán v katalogu neexistuje."
)
WEB_DIFF_REASON_NEW = "Pracoviště na oficiálním webu v katalogu chybí."
WEB_DIFF_REASON_CHANGED = "Údaje pracoviště se na oficiálním webu liší."
WEB_DIFF_REASON_PROTECTED = (
    "Záznam je ručně chráněný; webová data ho automaticky nepřepíší."
)
WEB_DIFF_REASON_MISSING = "Pracoviště se na oficiálním webu nenašlo."
WEB_DIFF_REASON_PROTECTED_MISSING = (
    "Ručně chráněné pracoviště se na oficiálním webu nenašlo."
)
WEB_DIFF_REASON_INACTIVE = (
    "Neaktivní pracoviště je na oficiálním webu stále uvedeno."
)
WEB_DIFF_REASON_DUPLICATE_NAME = (
    "Místní záznam má shodný název, ale jiný technický klíč."
)
WEB_DIFF_REASON_DUPLICATE_ADDRESS = (
    "Místní záznam má shodnou adresu, ale jiný technický klíč."
)
WEB_DIFF_REASON_DUPLICATE_CITY_SCOPE = (
    "Místní záznam má shodné město i územní působnost, ale jiný technický klíč."
)
WEB_DIFF_REASON_IDENTITY = (
    "Stejný technický klíč patří jinému kontrolnímu orgánu."
)
