"""Metadata a konstanty modulu Audity systémů řízení."""

from dataclasses import dataclass

MODULE_KEY = "audity"
MODULE_NAME = "Audity systémů řízení"
MODULE_DESCRIPTION = "Evidence interních auditů systémů řízení (BOZP, kvalita a další)."

AUDIT_STATUS_PLANOVANO = "Plánováno"
AUDIT_STATUS_PROBIHA = "Probíhá"
AUDIT_STATUS_DOKONCENO = "Dokončeno"

AUDIT_SPIS_STATUSES = (
    AUDIT_STATUS_PLANOVANO,
    AUDIT_STATUS_PROBIHA,
    AUDIT_STATUS_DOKONCENO,
)

DEFAULT_AUDIT_SPIS_STATUS = AUDIT_STATUS_PLANOVANO
VALID_AUDIT_STATUSES = frozenset(AUDIT_SPIS_STATUSES)

AUDIT_COMPLETION_CONFIRM_MESSAGE = (
    "Audit obsahuje otevřená zjištění nebo aktivní úkoly. "
    "Přesto ho chcete označit jako dokončený?"
)

AUDIT_TYPE_RADNY = "Řádný"
AUDIT_TYPE_MIMORADNY = "Mimořádný"

AUDIT_TYPES = (
    AUDIT_TYPE_RADNY,
    AUDIT_TYPE_MIMORADNY,
)

DEFAULT_AUDIT_TYPE = AUDIT_TYPE_RADNY

PLANNED_MONTH_NAMES = (
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

PLANNED_MONTH_NOT_SET_LABEL = "—"

AUDIT_STATUS_FILTER_PROBIHAJICI = "Probíhající"
AUDIT_STATUS_FILTER_PLANOVANE = "Plánované"
AUDIT_STATUS_FILTER_DOKONCENE = "Dokončené"
AUDIT_STATUS_FILTER_VSE = "Vše"

DEFAULT_AUDIT_STATUS_FILTER = AUDIT_STATUS_FILTER_PROBIHAJICI

AUDIT_STATUS_BY_FILTER = {
    AUDIT_STATUS_FILTER_PROBIHAJICI: AUDIT_STATUS_PROBIHA,
    AUDIT_STATUS_FILTER_PLANOVANE: AUDIT_STATUS_PLANOVANO,
    AUDIT_STATUS_FILTER_DOKONCENE: AUDIT_STATUS_DOKONCENO,
}

YEAR_FILTER_VSE = "Vše"

TAB_AUDITOVANE_PROCESY = "Řídicí procesy"

COMMISSION_RECORD_LEADER = "vedouci_komise"
COMMISSION_RECORD_WORKPLACE = "zastupce_pracoviste"
COMMISSION_RECORD_UNION = "zastupce_odboru"
COMMISSION_RECORD_MEMBER = "clen_komise"
COMMISSION_RECORD_INVITED = "prizvana_osoba"

COMMISSION_RECORD_TYPES = frozenset(
    {
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_WORKPLACE,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_MEMBER,
        COMMISSION_RECORD_INVITED,
    }
)

COMMISSION_REQUIRES_LEADER_MESSAGE = "Audit musí mít právě jednoho vedoucího auditora."
COMMISSION_REQUIRES_WORKPLACE_MESSAGE = "Audit musí mít právě jednoho zástupce auditovaného provozu."
COMMISSION_REQUIRES_UNION_MESSAGE = "Audit musí mít právě jednoho zástupce odborové organizace."
COMMISSION_UNKNOWN_RECORD_TYPE_MESSAGE = "Neznámý typ záznamu auditního týmu: {record_type}"
COMMISSION_MEMBER_NAME_REQUIRED_MESSAGE = "Každý člen auditního týmu musí mít vyplněné jméno."
COMMISSION_THP_ROLE_REQUIRED_MESSAGE = (
    "Vedoucí auditor, zástupce auditovaného provozu a auditoři musí být THP pracovníci."
)
COMMISSION_PERSON_ROLE_REQUIRED_MESSAGE = (
    "Zástupce odborové organizace a přizvané osoby musí být ze seznamu osob."
)

COMMISSION_MISSING_LEADER_MESSAGE = "Vyberte vedoucího auditora z THP pracovníků."
COMMISSION_MISSING_WORKPLACE_MESSAGE = "Vyberte zástupce auditovaného provozu z THP pracovníků."
COMMISSION_MISSING_UNION_MESSAGE = "Vyberte zástupce odborové organizace ze seznamu osob."

COMMISSION_DEFAULT_ROLE_MEMBER = "Auditor"
COMMISSION_DEFAULT_ROLE_INVITED = "Přizvaná osoba"
COMMISSION_DUPLICATE_PERSON_MESSAGE = "Tato osoba je již v auditním týmu zařazena."

COMMISSION_LABEL_LEADER = "Vedoucí auditor"
COMMISSION_LABEL_MEMBER = "Auditor"
COMMISSION_LABEL_WORKPLACE = "Zástupce auditovaného provozu"
COMMISSION_LABEL_UNION = "Zástupce odborové organizace"
COMMISSION_LABEL_INVITED = "Přizvané osoby"

TAB_AUDITOVANE_PROCESY = "Řídicí procesy"
TAB_WORKPLACE_HISTORY = "Historie pracoviště"

TAB_LABELS = (
    "Spis",
    "Komise",
    TAB_AUDITOVANE_PROCESY,
    TAB_WORKPLACE_HISTORY,
    "Zjištění",
    "Úkoly",
    "Závěr",
)

PROCESS_PANEL_LEFT_WIDTH = 260
METHODOLOGY_PANEL_MIN_WIDTH = 280
WORK_PANEL_STRETCH = 65
METHODOLOGY_PANEL_STRETCH = 35
METHODOLOGY_PANEL_TITLE = "Metodická podpora"
PROCESS_NOT_IMPLEMENTED_TEXT = "Tento řídicí proces zatím není implementován."
PROCESS_PART_NOT_IMPLEMENTED_TEXT = "Tato část bude doplněna."
KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT = PROCESS_PART_NOT_IMPLEMENTED_TEXT

GUIDE_BLOCK_UNDERSTAND = "Pochop proces"
GUIDE_BLOCK_VERIFY = "Ověř fungování"
GUIDE_BLOCK_EVALUATE = "Vyhodnoť"

GUIDE_LABEL_UCEL = "Účel procesu"
GUIDE_LABEL_WHY_IMPORTANT = "Proč je důležitý"
GUIDE_LABEL_EXPECTED_OUTPUT = "Očekávaný výstup procesu"
GUIDE_LABEL_PROCESS_LINKS = "Vazby na ostatní řídicí procesy"
GUIDE_LABEL_NORM_REQUIREMENTS = "Související požadavky norem"
GUIDE_LABEL_VERIFICATION_GOAL = "Cíl ověření"
GUIDE_LABEL_AREAS = "Oblasti ověření"
GUIDE_LABEL_OBJECTIVE_EVIDENCE = "Doporučené objektivní důkazy"
GUIDE_LABEL_RECOMMENDED_INTERVIEWS = "Doporučené rozhovory / role"
GUIDE_LABEL_OBSERVATIONS_IN_OPERATION = "Možné pozorování v provozu"
GUIDE_LABEL_TYPICAL_NONCONFORMITIES = "Typické neshody"

GUIDE_SELECT_AREA_FOR_EVALUATION = (
    "Vyberte oblast ověření ve stromu vlevo pro vyhodnocení auditních tvrzení."
)
KNOWLEDGE_REFERENCE_PHOTOS_TITLE = "📷 Referenční fotografie"
REFERENCE_PHOTO_THUMBNAIL_SIZE = 120
REFERENCE_PHOTO_PLACEHOLDER_WIDTH = 220
REFERENCE_PHOTO_PLACEHOLDER_ICON_SIZE_PX = 40
AUDIT_RESULT_HEADER_LABEL = "Výsledek auditu"
AUDIT_RESULT_NOTE_LABEL = "Poznámka auditora:"

FINDING_SOURCE_LABEL = "Audit systému řízení"
FINDING_DIALOG_TITLE = "Zjištění auditu"
FINDING_CREATE_FROM_CONTROL_POINT_LABEL = "➕ Založit zjištění"
FINDING_OPEN_EXISTING_LABEL = "Otevřít zjištění"
FINDING_CREATED_LABEL = "Zjištění založeno"
FINDING_DUPLICATE_MESSAGE = "Pro toto auditní tvrzení už existuje zjištění. Otevře se existující záznam."
AUDIT_MUST_BE_SAVED_MESSAGE = "Audit je nutné nejdříve uložit."
FINDING_REQUIRES_NONCOMPLIANCE_MESSAGE = (
    "Zjištění lze založit pouze u auditního tvrzení s výsledkem „Nevyhovuje“."
)

AUDIT_FINDING_TYPE_NESHODA = "neshoda"
AUDIT_FINDING_TYPE_PKZ = "prilezitost_zlepseni"
AUDIT_FINDING_TYPE_POZOROVANI = "pozorovani"

AUDIT_FINDING_TYPE_LABELS = {
    AUDIT_FINDING_TYPE_NESHODA: "Neshoda",
    AUDIT_FINDING_TYPE_PKZ: "PKZ",
    AUDIT_FINDING_TYPE_POZOROVANI: "Pozorování",
}

AUDIT_FINDING_TYPES = frozenset(AUDIT_FINDING_TYPE_LABELS.keys())

AUDIT_PROGRAM_STATUS_DRAFT = "draft"
AUDIT_PROGRAM_STATUS_APPROVED = "approved"
AUDIT_PROGRAM_STATUS_RUNNING = "running"
AUDIT_PROGRAM_STATUS_CLOSED = "closed"

AUDIT_PROGRAM_STATUSES = (
    AUDIT_PROGRAM_STATUS_DRAFT,
    AUDIT_PROGRAM_STATUS_APPROVED,
    AUDIT_PROGRAM_STATUS_RUNNING,
    AUDIT_PROGRAM_STATUS_CLOSED,
)

DEFAULT_AUDIT_PROGRAM_STATUS = AUDIT_PROGRAM_STATUS_DRAFT

AUDIT_PROGRAM_VISIT_STATUS_PLANNED = "planned"
AUDIT_PROGRAM_VISIT_STATUS_IN_PROGRESS = "in_progress"
AUDIT_PROGRAM_VISIT_STATUS_COMPLETED = "completed"
AUDIT_PROGRAM_VISIT_STATUS_SKIPPED = "skipped"

AUDIT_PROGRAM_VISIT_STATUSES = (
    AUDIT_PROGRAM_VISIT_STATUS_PLANNED,
    AUDIT_PROGRAM_VISIT_STATUS_IN_PROGRESS,
    AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_STATUS_SKIPPED,
)

DEFAULT_AUDIT_PROGRAM_VISIT_STATUS = AUDIT_PROGRAM_VISIT_STATUS_PLANNED

AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED = "planned"
AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED = "completed"
AUDIT_PROGRAM_VISIT_PROCESS_STATUS_SKIPPED = "skipped"

AUDIT_PROGRAM_VISIT_PROCESS_STATUSES = (
    AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED,
    AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_PROCESS_STATUS_SKIPPED,
)

DEFAULT_AUDIT_PROGRAM_VISIT_PROCESS_STATUS = AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED

AUDIT_STANDARD_ISO_45001 = "ISO 45001"
AUDIT_STANDARD_ISO_9001 = "ISO 9001"
AUDIT_STANDARD_ISO_14001 = "ISO 14001"

AUDIT_PROGRAM_STANDARDS_V1 = (
    AUDIT_STANDARD_ISO_45001,
    AUDIT_STANDARD_ISO_9001,
)

DEFAULT_AUDIT_PROGRAM_STANDARDS = AUDIT_PROGRAM_STANDARDS_V1

AUDIT_PROGRAM_BUTTON_LABEL = "Program auditů"
AUDIT_PROGRAM_WINDOW_TITLE = "Program auditů"
AUDIT_PROGRAM_ADD_BUTTON = "+ Nový program"
AUDIT_PROGRAM_LEFT_PANEL_TITLE = "Programy auditů"
AUDIT_PROGRAM_CENTER_PANEL_TITLE = "Detail programu"
AUDIT_PROGRAM_RIGHT_PANEL_TITLE = "Přehled programu"
AUDIT_PROGRAM_GENERATE_VISITS_BUTTON = "Generovat návštěvy"
AUDIT_PROGRAM_DISTRIBUTE_PROCESSES_BUTTON = "Rozdělit procesy"
AUDIT_PROGRAM_REFRESH_OVERVIEW_BUTTON = "Přepočítat přehled"
AUDIT_PROGRAM_CREATE_DIALOG_TITLE = "Nový program auditů"
AUDIT_PROGRAM_EDIT_DIALOG_TITLE = "Upravit program auditů"
AUDIT_PROGRAM_STATUS_VISITS_GENERATED = "✓ Návštěvy vygenerovány."
AUDIT_PROGRAM_STATUS_PROCESSES_DISTRIBUTED = "✓ Procesy rozděleny."
AUDIT_PROGRAM_STATUS_OVERVIEW_REFRESHED = "✓ Přehled přepočten."
AUDIT_PROGRAM_STATUS_PROGRAM_CREATED = "✓ Program vytvořen."
AUDIT_PROGRAM_STATUS_PROGRAM_UPDATED = "✓ Program upraven."
AUDIT_PROGRAM_STATUS_PROCESS_MOVED = "✓ Proces přesunut."
AUDIT_PROGRAM_STATUS_VISIT_CREATED = "✓ Návštěva vytvořena."
AUDIT_PROGRAM_STATUS_VISIT_UPDATED = "✓ Návštěva upravena."
AUDIT_PROGRAM_STATUS_VISIT_SKIPPED = "✓ Návštěva zrušena."
AUDIT_PROGRAM_STATUS_AUDIT_CREATED = "✓ Audit založen."
AUDIT_PROGRAM_STATUS_AUDIT_COMPLETED = "✓ Audit dokončen."

AUDIT_PROGRAM_START_AUDIT_BUTTON = "Zahájit audit..."
AUDIT_PROGRAM_OPEN_AUDIT_BUTTON = "Otevřít audit"
AUDIT_PROGRAM_VISIT_HAS_AUDIT = "Návštěva už má vytvořený audit."
AUDIT_PROGRAM_VISIT_NO_AUDIT = "Návštěva nemá vytvořený audit."

AUDIT_PROGRAM_MANUAL_GENERATE_BLOCKED = (
    "Program byl ručně upraven. Automatické generování návštěv je vypnuto."
)
AUDIT_PROGRAM_MANUAL_DISTRIBUTE_BLOCKED = (
    "Program byl ručně upraven. Automatické rozdělení procesů je vypnuto."
)

AUDIT_PROGRAM_ADD_VISIT_BUTTON = "+ Nová návštěva"
AUDIT_PROGRAM_MOVE_PROCESS_BUTTON = "Přesunout..."
AUDIT_PROGRAM_EDIT_VISIT_BUTTON = "Upravit návštěvu"
AUDIT_PROGRAM_SKIP_VISIT_BUTTON = "Zrušit návštěvu"
AUDIT_PROGRAM_NEW_VISIT_DIALOG_TITLE = "Nová návštěva"
AUDIT_PROGRAM_EDIT_VISIT_DIALOG_TITLE = "Upravit návštěvu"
AUDIT_PROGRAM_MOVE_PROCESS_DIALOG_TITLE = "Přesunout řídicí proces"
AUDIT_PROGRAM_VISIT_SKIPPED_SUFFIX = "(Zrušeno)"

AUDIT_PROGRAM_DASHBOARD_TAB_FINDINGS = "Zjištění"
AUDIT_PROGRAM_DASHBOARD_TAB_TASKS = "Úkoly"
AUDIT_PROGRAM_PLAN_TAB_TREE = "Plán návštěv"
AUDIT_PROGRAM_PLAN_TAB_VISITS = "Plánované návštěvy"
AUDIT_PROGRAM_DASHBOARD_FILTER_OPEN_ONLY = "Jen otevřená"
AUDIT_PROGRAM_DASHBOARD_FILTER_OVERDUE = "Jen po termínu"
AUDIT_PROGRAM_DASHBOARD_FILTER_SEVERE = "Jen závažná"

MONTH_NAMES_CAPITALIZED = tuple(
    name.capitalize()
    for name in PLANNED_MONTH_NAMES
)

AUDIT_PROGRAM_STATUS_LABELS = {
    AUDIT_PROGRAM_STATUS_DRAFT: "Příprava",
    AUDIT_PROGRAM_STATUS_APPROVED: "Schválený",
    AUDIT_PROGRAM_STATUS_RUNNING: "Probíhá",
    AUDIT_PROGRAM_STATUS_CLOSED: "Uzavřený",
}

AUDIT_PROGRAM_STATUS_BADGE_ICONS = {
    AUDIT_PROGRAM_STATUS_DRAFT: "🟡",
    AUDIT_PROGRAM_STATUS_APPROVED: "🟢",
    AUDIT_PROGRAM_STATUS_RUNNING: "🔵",
    AUDIT_PROGRAM_STATUS_CLOSED: "⚫",
}

AUDIT_PROGRAM_PLANNED_VISITS_COLUMN_TERM = "Termín"

AUDIT_PROGRAM_VISIT_STATUS_LABELS = {
    AUDIT_PROGRAM_VISIT_STATUS_PLANNED: "Plánováno",
    AUDIT_PROGRAM_VISIT_STATUS_IN_PROGRESS: "Probíhá",
    AUDIT_PROGRAM_VISIT_STATUS_COMPLETED: "Dokončeno",
    AUDIT_PROGRAM_VISIT_STATUS_SKIPPED: "Zrušeno",
}

AUDIT_PROGRAM_OVERVIEW_COLUMNS = (
    "Pracoviště",
    "Počet návštěv",
    "Procesů",
    "Splněno",
    "%",
)

PROCESS_TERM_PROCESS = "Řídicí proces"
PROCESS_TERM_CRITERION = "Oblast ověření"
PROCESS_TERM_QUESTION = "Auditní tvrzení"

KNOWLEDGE_EDITOR_BUTTON_LABEL = "Editor metodiky"
KNOWLEDGE_EDITOR_SAVED_MESSAGE = "✓ Uloženo."
KNOWLEDGE_EDITOR_ADD_PROCESS_BUTTON = "+ Přidat řídicí proces"
KNOWLEDGE_EDITOR_WINDOW_TITLE = "Editor metodiky auditora"
KNOWLEDGE_EDITOR_USER_COPY_HINT = (
    "Upravujete uživatelskou kopii metodiky v "
    "~/.local/share/manazer-bozp/ciselniky/audity/."
)
KNOWLEDGE_EDITOR_EDIT_PLACEHOLDER = (
    "Editace metodiky bude doplněna v další verzi."
)
KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT = (
    "Vyberte řídicí proces nebo oblast ověření ve stromu vlevo."
)
KNOWLEDGE_EDITOR_ASSERTIONS_PLACEHOLDER = (
    "Auditní tvrzení budou editovatelná v další verzi."
)
KNOWLEDGE_EDITOR_TAB_PLACEHOLDER = (
    "Tato část bude implementována v dalších commitech."
)
KNOWLEDGE_EDITOR_SECTION_TABS = (
    "Auditní tvrzení",
    "Objektivní důkazy",
    "Rozhovory",
    "Pozorování v provozu",
    "Typické neshody",
    "PKZ",
    "Pozorování",
    "Vazby",
    "Normy",
    "Postup kontroly",
    "Referenční fotografie",
)

KNOWLEDGE_EDITOR_SECTION_LIST_TABS: tuple[tuple[str, str], ...] = (
    ("Objektivní důkazy", "objektivni_dukazy"),
    ("Rozhovory", "doporucene_rozhovory"),
    ("Pozorování v provozu", "pozorovani_v_provozu"),
    ("Typické neshody", "typicke_neshody"),
    ("PKZ", "pkz"),
    ("Pozorování", "pozorovani"),
    ("Vazby", "vazby_procesy"),
    ("Normy", "pozadavky_normy"),
)

KNOWLEDGE_EDITOR_SECTION_LIST_FIELDS = frozenset(
    field_name for _title, field_name in KNOWLEDGE_EDITOR_SECTION_LIST_TABS
)

KNOWLEDGE_EDITOR_SECTION_POSTUP_TAB = ("Postup kontroly", "postup_kontroly")
KNOWLEDGE_EDITOR_SECTION_REFERENCE_PHOTO_TAB = (
    "Referenční fotografie",
    "referencni_fotografie",
)

KNOWLEDGE_EDITOR_SECTION_EXTENDED_LIST_FIELDS = frozenset(
    {
        KNOWLEDGE_EDITOR_SECTION_POSTUP_TAB[1],
        KNOWLEDGE_EDITOR_SECTION_REFERENCE_PHOTO_TAB[1],
    }
)

KNOWLEDGE_EDITOR_SECTION_EDITABLE_LIST_FIELDS = (
    KNOWLEDGE_EDITOR_SECTION_LIST_FIELDS | KNOWLEDGE_EDITOR_SECTION_EXTENDED_LIST_FIELDS
)

CONTROL_POINT_HISTORY_EMPTY = "Zatím bez historie."
CONTROL_POINT_HISTORY_SELECT = "Vyberte auditní tvrzení vlevo."
CONTROL_POINT_HISTORY_LIMIT = 5
CONTROL_POINT_HISTORY_WORKPLACE_TITLE = "Historie tohoto auditovaného provozu"
CONTROL_POINT_SHARED_EXPERIENCES_TITLE = "Sdílené zkušenosti"
CONTROL_POINT_HISTORY_WORKPLACE_NO_WORKPLACE = "Pro zobrazení historie vyberte auditovaný provoz."
CONTROL_POINT_SHARED_EXPERIENCES_EMPTY = "Zatím bez sdílených zkušeností."

CONTROL_POINT_SEVERITY_KRITICKA = "kriticka"
CONTROL_POINT_SEVERITY_VYSOKA = "vysoka"
CONTROL_POINT_SEVERITY_STREDNI = "stredni"
CONTROL_POINT_SEVERITY_NIZKA = "nizka"
CONTROL_POINT_SEVERITY_DEFAULT = CONTROL_POINT_SEVERITY_STREDNI

CONTROL_POINT_SEVERITY_OPTIONS = (
    (CONTROL_POINT_SEVERITY_KRITICKA, "Kritická"),
    (CONTROL_POINT_SEVERITY_VYSOKA, "Vysoká"),
    (CONTROL_POINT_SEVERITY_STREDNI, "Střední"),
    (CONTROL_POINT_SEVERITY_NIZKA, "Nízká"),
)


def audit_finding_type_label(finding_type: str) -> str:
    return AUDIT_FINDING_TYPE_LABELS.get(finding_type, finding_type)


@dataclass(frozen=True)
class AuditFindingKnowledgeContext:
    area_id: str
    area_label: str
    section_id: str
    section_label: str
    control_point_id: str
    control_point_label: str
    question_stable_key: str = ""
