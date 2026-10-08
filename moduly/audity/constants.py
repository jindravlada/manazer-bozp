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

AUDIT_CONCLUSION_LABEL = "Závěr auditu"
AUDIT_CONCLUSION_REQUIRED_MESSAGE = (
    "Audit nelze dokončit. Vyplňte závěr auditu."
)
AUDIT_EXPECTED_END_BEFORE_START_MESSAGE = (
    "Předpokládané datum ukončení nesmí být dříve než datum zahájení."
)
AUDIT_CONCLUSION_EXPORT_SECTION = "Závěr auditu"
AUDIT_STRENGTHS_EXPORT_SECTION = "Silné stránky"

AUDIT_LEAD_RECOMMENDATION_LABEL = "Doporučení vedoucího auditora"
AUDIT_LEAD_RECOMMENDATION_GENERATE_BUTTON = "Vytvořit doporučení podle výsledků"
AUDIT_LEAD_RECOMMENDATION_STATUS_CURRENT = "Aktuální"
AUDIT_LEAD_RECOMMENDATION_STATUS_STALE = (
    "Neaktuální – výsledky auditu se změnily"
)
AUDIT_LEAD_RECOMMENDATION_STATUS_UNCONFIRMED = (
    "Automatický návrh dosud nebyl potvrzen"
)
AUDIT_LEAD_RECOMMENDATION_REQUIRED_MESSAGE = (
    "Audit nelze dokončit. Vyplňte doporučení vedoucího auditora."
)
AUDIT_LEAD_RECOMMENDATION_SIGNATURE_INVALID_MESSAGE = (
    "Audit nelze dokončit. Doporučení vedoucího auditora neodpovídá "
    "aktuálním výsledkům."
)
AUDIT_LEAD_RECOMMENDATION_EMPTY_REVIEW_MESSAGE = (
    "Byl vytvořen návrh doporučení vedoucího auditora. "
    "Před dokončením jej zkontrolujte."
)
AUDIT_LEAD_RECOMMENDATION_STALE_REVIEW_MESSAGE = (
    "Výsledky auditu se od vytvoření doporučení změnily. "
    "Doporučení zkontrolujte nebo vytvořte nový návrh."
)
AUDIT_LEAD_RECOMMENDATION_REPLACE_CONFIRM = (
    "Současný text doporučení vedoucího auditora bude nahrazen "
    "automatickým návrhem. Chcete ho nahradit?"
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
COMMISSION_REQUIRES_WORKPLACE_MESSAGE = "Audit musí mít právě jednoho zástupce provozu."
COMMISSION_REQUIRES_UNION_MESSAGE = "Audit musí mít právě jednoho zástupce odborové organizace."
COMMISSION_UNKNOWN_RECORD_TYPE_MESSAGE = "Neznámý typ záznamu auditního týmu: {record_type}"
COMMISSION_MEMBER_NAME_REQUIRED_MESSAGE = "Každý člen auditního týmu musí mít vyplněné jméno."
COMMISSION_THP_ROLE_REQUIRED_MESSAGE = (
    "Vedoucí auditor, zástupce provozu a auditoři musí být THP pracovníci."
)
COMMISSION_PERSON_ROLE_REQUIRED_MESSAGE = (
    "Zástupce odborové organizace a přizvané osoby musí být ze seznamu osob."
)

COMMISSION_MISSING_LEADER_MESSAGE = "Vyberte vedoucího auditora z THP pracovníků."
COMMISSION_MISSING_WORKPLACE_MESSAGE = "Vyberte zástupce provozu z THP pracovníků."
COMMISSION_MISSING_UNION_MESSAGE = "Vyberte zástupce odborové organizace ze seznamu osob."

COMMISSION_DEFAULT_ROLE_MEMBER = "Auditor"
COMMISSION_DEFAULT_ROLE_INVITED = "Přizvaná osoba"
COMMISSION_DUPLICATE_PERSON_MESSAGE = "Tato osoba je již v auditním týmu zařazena."

COMMISSION_LABEL_LEADER = "Vedoucí auditor"
COMMISSION_LABEL_MEMBER = "Auditor"
COMMISSION_LABEL_WORKPLACE = "Zástupce provozu"
COMMISSION_LABEL_UNION = "Zástupce odborové organizace"
COMMISSION_LABEL_INVITED = "Přizvané osoby"

TAB_AUDITOVANE_PROCESY = "Řídicí procesy"
TAB_DOCUMENTACE = "Dokumentace"
TAB_TEREN = "Terén"
TAB_MIMORADNE = "Mimořádné ověření"
TAB_UVOD = "Úvod"
# Zpětná kompatibilita aliasu (AUDIT-INTRO-1 přejmenovalo záložku).
TAB_WORKPLACE_HISTORY = TAB_UVOD

TAB_LABELS = (
    "Spis",
    "Komise",
    TAB_UVOD,
    TAB_DOCUMENTACE,
    TAB_TEREN,
    TAB_MIMORADNE,
    "Zjištění",
    "Úkoly",
    "Závěr",
)

AUDIT_INTRO_FIRST_AUDIT_MESSAGE = (
    "Jedná se o první audit tohoto provozu. "
    "Historie předchozích auditů zatím není k dispozici."
)
AUDIT_INTRO_CHANGES_LABEL = "Změny od posledního auditu"
AUDIT_INTRO_CHANGES_EMPTY = "Změny od posledního auditu nebyly uvedeny."
AUDIT_INTRO_NO_WORKPLACE_HINT = (
    "Úvod bude dostupný po výběru auditovaného provozu."
)
AUDIT_INTRO_PREVIOUS_AUDITS_GROUP = "Předchozí audity"
AUDIT_INTRO_FINDINGS_GROUP = "Zjištění z předchozích auditů"
AUDIT_INTRO_TASKS_GROUP = "Úkoly z předchozích auditů"
# Podrobná zpráva: mezititulky s dvojtečkou. Záložka Úvod zůstává bez dvojtečky.
AUDIT_INTRO_EXPORT_CHANGES_HEADING = f"{AUDIT_INTRO_CHANGES_LABEL}:"
AUDIT_INTRO_EXPORT_PREVIOUS_AUDITS_HEADING = f"{AUDIT_INTRO_PREVIOUS_AUDITS_GROUP}:"
AUDIT_INTRO_EXPORT_FINDINGS_HEADING = f"{AUDIT_INTRO_FINDINGS_GROUP}:"
AUDIT_INTRO_EXPORT_TASKS_HEADING = f"{AUDIT_INTRO_TASKS_GROUP}:"
AUDIT_INTRO_NO_HISTORICAL_FINDINGS = "Žádná zjištění z předchozích auditů."
AUDIT_INTRO_NO_HISTORICAL_TASKS = (
    "Žádné úkoly navázané na zjištění z předchozích auditů."
)
AUDIT_INTRO_CONTINUITY_SECTION = "Návaznost na předchozí audity"
AUDIT_INTRO_EXPORT_SECTION = "Úvod"

MOVE_TO_TERRAIN_LABEL = "→ Terén"
MOVE_TO_DOCUMENTATION_LABEL = "→ Dokumentace"
MOVE_VERIFICATION_TYPE_TOOLTIP = (
    "Změní typ ověření jen pro tento audit. Metodika zůstane beze změny."
)

TERRAIN_CHECKLIST_BUTTON_LABEL = "Vytisknout terénní checklist"
TERRAIN_CHECKLIST_DIALOG_TITLE = "Terénní checklist"
TERRAIN_CHECKLIST_TOOLTIP = (
    "Pracovní checklist auditních tvrzení pro ověření v provozu."
)
TERRAIN_CHECKLIST_EMPTY = "Nejsou žádná auditní tvrzení typu Terén."
TERRAIN_CHECKLIST_REQUIRES_SAVED = "Audit je nutné nejdříve uložit."

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
FINDING_REQUIRES_RESULT_MESSAGE = (
    "Zjištění lze založit pouze u auditního tvrzení s výsledkem "
    "„Nevyhovuje“ nebo „Vyhovuje s doporučením“."
)

AUDIT_FINDING_TYPE_NESHODA = "neshoda"
AUDIT_FINDING_TYPE_PKZ = "prilezitost_zlepseni"
AUDIT_FINDING_TYPE_POZOROVANI = "pozorovani"

AUDIT_FINDING_TYPE_LABELS = {
    AUDIT_FINDING_TYPE_NESHODA: "Neshoda",
    AUDIT_FINDING_TYPE_PKZ: "Příležitost ke zlepšování",
    AUDIT_FINDING_TYPE_POZOROVANI: "Pozorování",
}

AUDIT_FINDING_TYPES = frozenset(AUDIT_FINDING_TYPE_LABELS.keys())

# Pořadí druhů v úvodu zprávy podle závažnosti ISO 19011:
# neshoda → pozorování → příležitost ke zlepšení.
AUDIT_FINDING_REPORT_TYPE_ORDER: tuple[str, ...] = (
    AUDIT_FINDING_TYPE_NESHODA,
    AUDIT_FINDING_TYPE_POZOROVANI,
    AUDIT_FINDING_TYPE_PKZ,
)

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

AUDIT_PROGRAM_BUTTON_LABEL = "Manažer auditů"
AUDIT_PROGRAM_WINDOW_TITLE = "Program auditů"
AUDIT_PROGRAM_MANAGER_BANNER_TITLE = "Manažer auditů"
AUDIT_PROGRAM_MANAGER_BANNER_ACTIVE_PROGRAM = "Aktivní program"
AUDIT_PROGRAM_MANAGER_BANNER_NEAREST_VISIT = "Nejbližší návštěva"
AUDIT_PROGRAM_MANAGER_BANNER_OPEN_FINDINGS = "Otevřená zjištění"
AUDIT_PROGRAM_MANAGER_BANNER_OPEN_TASKS = "Otevřené úkoly"
AUDIT_PROGRAM_MANAGER_NO_PROGRAM_TEXT = "Zatím není založen žádný program auditů."
AUDIT_PROGRAM_ADD_BUTTON = "+ Nový program"
AUDIT_PROGRAM_LEFT_PANEL_TITLE = "Programy auditů"
AUDIT_PROGRAM_CENTER_PANEL_TITLE = "Detail programu"
AUDIT_PROGRAM_DETAIL_STANDARDS_LABEL = "Normy:"
AUDIT_PROGRAM_DETAIL_ACTIONS_LABEL = "Akce:"
AUDIT_PROGRAM_RIGHT_PANEL_TITLE = "Přehled programu"
AUDIT_PROGRAM_GENERATE_VISITS_BUTTON = "Generovat návštěvy"
AUDIT_PROGRAM_SUPPLEMENT_WORKPLACES_BUTTON = "Doplnit pracoviště"
AUDIT_PROGRAM_DISTRIBUTE_PROCESSES_BUTTON = "Rozdělit procesy"
AUDIT_PROGRAM_SUPPLEMENT_PROCESSES_BUTTON = "Doplnit nové procesy"
AUDIT_PROGRAM_USE_SUPPLEMENT_PROCESSES_LABEL = False
AUDIT_PROGRAM_REFRESH_OVERVIEW_BUTTON = "Přepočítat přehled"
AUDIT_PROGRAM_EXPORT_PLAN_BUTTON = "Exportovat plán"
AUDIT_PROGRAM_EXPORT_PLAN_BUTTON_SHORT = "Tisk plánu"
AUDIT_PROGRAM_EXPORT_PLAN_TOOLTIP = "Vytisknout auditní plán"
AUDIT_PROGRAM_EXPORT_PLAN_DIALOG_TITLE = "Exportovat plán interních auditů"
AUDIT_PROGRAM_EXPORT_PLAN_OPEN_FAILED = (
    "Plán byl exportován, ale nepodařilo se jej otevřít. Otevřete jej prosím ručně."
)
AUDIT_PROGRAM_PRINT_STATEMENTS_BUTTON = "Vytisknout auditní tvrzení"
AUDIT_PROGRAM_PRINT_STATEMENTS_DIALOG_TITLE = "Vytisknout auditní tvrzení"
AUDIT_PROGRAM_PRINT_STATEMENTS_DOCUMENT_TITLE = "Auditní tvrzení"
AUDIT_PROGRAM_PRINT_STATEMENTS_EMPTY = (
    "Vybraná návštěva nemá žádná použitelná auditní tvrzení."
)
AUDIT_PROGRAM_PRINT_STATEMENTS_OPEN_FAILED = (
    "Auditní tvrzení byla vygenerována, ale nepodařilo se je otevřít. "
    "Otevřete je prosím ručně."
)
AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_CURRENT = (
    "Aktuální metodika – audit dosud nebyl zahájen"
)
AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_FROZEN = "Zmrazená metodika auditu č. {number}"
AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_V = "V – Vyhovuje"
AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_VD = "VD – Vyhovuje s doporučením"
AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_N = "N – Nevyhovuje"
AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_NP = "NP – Nelze posoudit"
AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_MARKS = "V / VD / N / NP"
AUDIT_PROGRAM_FINAL_REPORT_BUTTON = "Závěrečná zpráva programu"
AUDIT_PROGRAM_PREVIOUS_PROGRAM_LABEL = "Navazuje na program:"


def audit_program_distribute_processes_button_label(has_existing_processes: bool) -> str:
    """Popisek tlačítka rozdělení procesů — připraveno pro budoucí přepnutí."""
    if AUDIT_PROGRAM_USE_SUPPLEMENT_PROCESSES_LABEL and has_existing_processes:
        return AUDIT_PROGRAM_SUPPLEMENT_PROCESSES_BUTTON
    return AUDIT_PROGRAM_DISTRIBUTE_PROCESSES_BUTTON
AUDIT_PROGRAM_CREATE_DIALOG_TITLE = "Nový program auditů"
AUDIT_PROGRAM_EDIT_DIALOG_TITLE = "Upravit program auditů"
AUDIT_PROGRAM_STATUS_VISITS_GENERATED = "✓ Návštěvy vygenerovány."
AUDIT_PROGRAM_STATUS_WORKPLACES_SUPPLEMENTED = "✓ Pracoviště doplněna."
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

AUDIT_PROGRAM_START_AUDIT_BUTTON = "Založit plán auditu..."
AUDIT_PROGRAM_START_AUDIT_BUTTON_SHORT = "Založit plán"
AUDIT_PROGRAM_OPEN_AUDIT_BUTTON = "Otevřít audit"
AUDIT_PROTOCOL_BUTTON_LABEL = "Protokol z interního auditu..."
AUDIT_PROTOCOL_BUTTON_SHORT = "Protokol"
AUDIT_PROTOCOL_DIALOG_TITLE = "Protokol z interního auditu"
AUDIT_DETAILED_REPORT_BUTTON_LABEL = "Podrobná zpráva z interního auditu..."
AUDIT_DETAILED_REPORT_BUTTON_SHORT = "Podrobná zpráva"
AUDIT_DETAILED_REPORT_DIALOG_TITLE = "Podrobná zpráva z interního auditu"
AUDITED_SYSTEM_LABEL = "Systém managementu BOZP a QMS"
AUDIT_PROGRAM_VISIT_HAS_AUDIT = "Návštěva už má vytvořený audit."
AUDIT_PROGRAM_VISIT_STARTED_ELSEWHERE = (
    "Tuto návštěvu mezitím zahájil jiný proces. Nový audit nevznikl."
)
AUDIT_PROGRAM_VISIT_NO_AUDIT = "Návštěva nemá vytvořený audit."
AUDIT_START_DATE_REQUIRED_MESSAGE = "Vyplňte datum zahájení auditu."
AUDIT_PREPARE_BUTTON = "Připravit audit"
AUDIT_PREPARED_ON_LABEL = "Audit připraven dne {date}"
AUDIT_PREPARE_CONFIRM_MESSAGE = (
    "Přípravou auditu bude vytvořen snapshot aktuálních auditních tvrzení "
    "a mimořádných ověření.\n\n"
    "Další změny metodiky se již do tohoto auditu automaticky nepromítnou.\n\n"
    "Chcete audit připravit?"
)
AUDIT_NOT_PREPARED_TAB_MESSAGE = (
    "Audit ještě není připraven. Nejprve použijte na záložce Spis funkci Připravit audit."
)
AUDIT_EXECUTION_REQUIRES_PREPARATION_MESSAGE = (
    "Audit ještě není připraven. Nejprve použijte na záložce Spis funkci Připravit audit."
)
AUDIT_EXECUTION_REQUIRES_SAVE_THEN_PREPARE_MESSAGE = (
    "Audit je nutné nejprve uložit a připravit."
)
AUDIT_SCOPE_GROUP = "Rozsah auditu"
AUDIT_SCOPE_SELECT_ALL = "Vybrat vše"
AUDIT_SCOPE_CLEAR = "Zrušit výběr"
AUDIT_SCOPE_SUMMARY = "Vybráno: {selected} z {total} procesů"
AUDIT_SCOPE_REQUIRED_MESSAGE = (
    "Nejprve zvolte alespoň jeden řídicí proces v rozsahu auditu."
)
AUDIT_SCOPE_UNAVAILABLE_MESSAGE = (
    "Rozsah auditu obsahuje řídicí proces, který už není v metodice dostupný: {names}. "
    "Upravte rozsah před přípravou auditu."
)
AUDIT_COMPLETION_REQUIRES_PREPARATION_MESSAGE = (
    "Audit nelze dokončit. Nejprve použijte na záložce Spis funkci Připravit audit."
)
AUDIT_COMPLETION_REQUIRES_START_DATE_MESSAGE = (
    "Audit nelze dokončit. Vyplňte datum zahájení auditu."
)
AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_UNFROZEN = (
    "Aktuální metodika – audit ještě není připraven, metodika není zmrazena"
)

AUDIT_PROGRAM_MANUAL_GENERATE_BLOCKED = (
    "Program byl ručně upraven. Automatické generování návštěv je vypnuto."
)
AUDIT_PROGRAM_MANUAL_DISTRIBUTE_BLOCKED = (
    "Program byl ručně upraven. Automatické rozdělení procesů je vypnuto."
)

AUDIT_PROGRAM_ADD_VISIT_BUTTON = "+ Nová návštěva"
AUDIT_PROGRAM_ADD_VISIT_BUTTON_SHORT = "+ Návštěva"
AUDIT_PROGRAM_MOVE_PROCESS_BUTTON = "Přesunout..."
AUDIT_PROGRAM_EDIT_VISIT_BUTTON = "Upravit návštěvu"
AUDIT_PROGRAM_EDIT_VISIT_BUTTON_SHORT = "Upravit"
AUDIT_PROGRAM_SKIP_VISIT_BUTTON = "Zrušit návštěvu"
AUDIT_PROGRAM_SKIP_VISIT_BUTTON_SHORT = "Zrušit"
AUDIT_PROGRAM_NEW_VISIT_DIALOG_TITLE = "Nová návštěva"
AUDIT_PROGRAM_EDIT_VISIT_DIALOG_TITLE = "Upravit návštěvu"
AUDIT_PROGRAM_MOVE_PROCESS_DIALOG_TITLE = "Přesunout řídicí proces"
AUDIT_PROGRAM_SUPPLEMENT_WORKPLACES_DIALOG_TITLE = "Doplnit pracoviště do programu"
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
    AUDIT_PROGRAM_STATUS_DRAFT: "Rozpracováno",
    AUDIT_PROGRAM_STATUS_APPROVED: "Schváleno",
    AUDIT_PROGRAM_STATUS_RUNNING: "Probíhá",
    AUDIT_PROGRAM_STATUS_CLOSED: "Uzavřeno",
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
    AUDIT_PROGRAM_VISIT_STATUS_COMPLETED: "Uzavřeno",
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
KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_LABEL = "Řídicí proces:"
KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_EMPTY = "—"
KNOWLEDGE_EDITOR_ASSERTIONS_PLACEHOLDER = (
    "Auditní tvrzení budou editovatelná v další verzi."
)
KNOWLEDGE_EDITOR_TAB_PLACEHOLDER = (
    "Tato část bude implementována v dalších commitech."
)

# AUDIT-METHOD-V2b: systémový provoz a druh otázky v editoru.
KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_LABEL = "Systémový provoz:"
KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_NONE = "Nevybráno"
KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_HINT = (
    "Otázky typu Systém se použijí pouze při auditu tohoto provozu."
)
KNOWLEDGE_EDITOR_QUESTION_KIND_LABEL = "Druh otázky:"
KNOWLEDGE_EDITOR_UNCLASSIFIED_COUNT_LABEL = "Nezařazené otázky: {count}"
KNOWLEDGE_EDITOR_QUESTION_KIND_REQUIRED = (
    "Vyberte druh otázky Systém nebo Provoz. Nezařazeno nelze uložit."
)

QUESTION_KIND_EDITOR_LABEL_UNCLASSIFIED = "Nezařazeno"
QUESTION_KIND_EDITOR_LABEL_SYSTEM = "Systém"
QUESTION_KIND_EDITOR_LABEL_OPERATION = "Provoz"

AUDIT_START_MISSING_SYSTEM_WORKPLACE = (
    "Nejdříve v editoru auditních otázek vyberte systémový provoz."
)
AUDIT_START_UNCLASSIFIED_QUESTIONS = (
    "Audit nelze zahájit. V plánovaných procesech zůstávají nezařazené auditní otázky."
)
AUDIT_START_UNCLASSIFIED_MAX_ITEMS = 12

PRE_AUDIT_METHOD_V2_BACKUP_PREFIX = "pre_audit_method_v2"
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

# AUDIT-SNAPSHOT-0: zdroj metodiky auditu (nullable = živá metodika / legacy).
AUDIT_METHODOLOGY_SOURCE_LIVE = "live"
AUDIT_METHODOLOGY_SOURCE_SNAPSHOT = "snapshot"
AUDIT_METHODOLOGY_SOURCES = (
    AUDIT_METHODOLOGY_SOURCE_LIVE,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
)
DEFAULT_AUDIT_METHODOLOGY_SOURCE = AUDIT_METHODOLOGY_SOURCE_LIVE

# AUDIT-SNAPSHOT-1a: generace a druh otázky pro historický backfill.
AUDIT_METHODOLOGY_GENERATION_LEGACY_V1 = "legacy-v1"
AUDIT_QUESTION_KIND_LEGACY = "legacy"

# AUDIT-METHOD-V2a: generace a druhy otázek nové metodiky.
AUDIT_METHODOLOGY_GENERATION_V2 = "v2"
# AUDIT-PLANNING-PREP-1: plán z programu, snapshot ještě nevznikl.
AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1 = "planned-unfrozen-v1"

AUDIT_QUESTION_KIND_SYSTEM = "system"
AUDIT_QUESTION_KIND_OPERATION = "operation"
AUDIT_QUESTION_KIND_EXTRAORDINARY = "extraordinary"
AUDIT_QUESTION_KIND_UNCLASSIFIED = "unclassified"

# Zpětná kompatibilita rezervovaného názvu (dříve „provoz“).
AUDIT_QUESTION_KIND_WORKPLACE = AUDIT_QUESTION_KIND_OPERATION

AUDIT_QUESTION_KINDS_V2 = (
    AUDIT_QUESTION_KIND_SYSTEM,
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    AUDIT_QUESTION_KIND_UNCLASSIFIED,
    AUDIT_QUESTION_KIND_LEGACY,
)

# Druhy povolené v nové JSON metodice (legacy jen historické snapshoty).
AUDIT_QUESTION_KINDS_LIVE_METHODOLOGY = (
    AUDIT_QUESTION_KIND_SYSTEM,
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    AUDIT_QUESTION_KIND_UNCLASSIFIED,
)

# Efektivní sada standardního snapshotu v2 (bez extraordinary / unclassified).
AUDIT_QUESTION_KINDS_V2_SNAPSHOT = (
    AUDIT_QUESTION_KIND_SYSTEM,
    AUDIT_QUESTION_KIND_OPERATION,
)

QUESTION_KIND_EDITOR_OPTIONS = (
    (AUDIT_QUESTION_KIND_UNCLASSIFIED, QUESTION_KIND_EDITOR_LABEL_UNCLASSIFIED),
    (AUDIT_QUESTION_KIND_SYSTEM, QUESTION_KIND_EDITOR_LABEL_SYSTEM),
    (AUDIT_QUESTION_KIND_OPERATION, QUESTION_KIND_EDITOR_LABEL_OPERATION),
)

# Globální nastavení systémového provozu (AUDIT-METHOD-V2a).
SYSTEM_AUDIT_WORKPLACE_SETTING_KEY = "system_audit_workplace_id"
SYSTEM_AUDIT_WORKPLACE_SETTINGS_FILE = "audity_nastaveni.json"

# AUDIT-EXTRAORDINARY-1/2: evidence + přiřazení mimořádných otázek.
EXTRAORDINARY_QUESTIONS_BUTTON_LABEL = "Mimořádné ověření"
EXTRAORDINARY_QUESTIONS_DIALOG_TITLE = "Mimořádné ověření"
EXTRAORDINARY_QUESTION_EDITOR_TITLE_NEW = "Nová mimořádná otázka"
EXTRAORDINARY_QUESTION_EDITOR_TITLE_EDIT = "Upravit mimořádnou otázku"

EXTRAORDINARY_QUESTION_STATUS_ACTIVE = "active"
EXTRAORDINARY_QUESTION_STATUS_COMPLETED = "completed"
EXTRAORDINARY_QUESTION_STATUS_CANCELLED = "cancelled"
EXTRAORDINARY_QUESTION_STATUSES = (
    EXTRAORDINARY_QUESTION_STATUS_ACTIVE,
    EXTRAORDINARY_QUESTION_STATUS_COMPLETED,
    EXTRAORDINARY_QUESTION_STATUS_CANCELLED,
)
EXTRAORDINARY_QUESTION_STATUS_LABELS = {
    EXTRAORDINARY_QUESTION_STATUS_ACTIVE: "Aktivní",
    EXTRAORDINARY_QUESTION_STATUS_COMPLETED: "Dokončeno",
    EXTRAORDINARY_QUESTION_STATUS_CANCELLED: "Zrušeno",
}

EXTRAORDINARY_TARGET_STATUS_PENDING = "pending"
EXTRAORDINARY_TARGET_STATUS_ASSIGNED = "assigned"
EXTRAORDINARY_TARGET_STATUS_VERIFIED = "verified"
EXTRAORDINARY_TARGET_STATUS_CANCELLED = "cancelled"
EXTRAORDINARY_TARGET_STATUSES = (
    EXTRAORDINARY_TARGET_STATUS_PENDING,
    EXTRAORDINARY_TARGET_STATUS_ASSIGNED,
    EXTRAORDINARY_TARGET_STATUS_VERIFIED,
    EXTRAORDINARY_TARGET_STATUS_CANCELLED,
)
EXTRAORDINARY_TARGET_STATUS_LABELS = {
    EXTRAORDINARY_TARGET_STATUS_PENDING: "Čeká na ověření",
    EXTRAORDINARY_TARGET_STATUS_ASSIGNED: "Přiřazeno",
    EXTRAORDINARY_TARGET_STATUS_VERIFIED: "Ověřeno",
    EXTRAORDINARY_TARGET_STATUS_CANCELLED: "Zrušeno",
}

EXTRAORDINARY_SYSTEM_WORKPLACE_MARK = " (systémový)"
EXTRAORDINARY_QUESTION_TEXT_REQUIRED = "Zadejte text mimořádné otázky."
EXTRAORDINARY_SEVERITY_REQUIRED = "Vyberte závažnost mimořádné otázky."
EXTRAORDINARY_VERIFICATION_TYPE_REQUIRED = "Vyberte typ ověření (Dokumentace nebo Terén)."
EXTRAORDINARY_VERIFICATION_TYPE_LEGACY_LABEL = "Neuvedeno"
EXTRAORDINARY_PROCESS_NONE_LABEL = "Mimořádná ověření"
EXTRAORDINARY_CHECKLIST_SECTION_TITLE = "Mimořádné ověření"
EXTRAORDINARY_EXPORT_SECTION_TITLE = "Mimořádné ověření"
EXTRAORDINARY_ANNUAL_SUMMARY_TITLE = "Mimořádná ověření"
EXTRAORDINARY_TARGET_REQUIRED = "Vyberte alespoň jeden cílový provoz."
EXTRAORDINARY_DUPLICATE_TARGET = "Cílový provoz je v otázce už evidován."
EXTRAORDINARY_TARGET_LOCKED = (
    "Cíl ve stavu Přiřazeno nebo Ověřeno nelze odstranit ani změnit na jiný provoz."
)
EXTRAORDINARY_TEXT_LOCKED = (
    "Text otázky nelze měnit po prvním přiřazení k auditu."
)
EXTRAORDINARY_CANCEL_BLOCKED = (
    "Otázku nelze zrušit, dokud má cíle ve stavu Přiřazeno nebo Ověřeno."
)
EXTRAORDINARY_NON_AUDITABLE_TARGET_LABEL = "Neauditovatelný cíl"
EXTRAORDINARY_NON_AUDITABLE_RESTORE_BLOCKED = (
    "Neauditovatelný cíl nelze obnovit. Zvolte aktivní auditovatelný provoz."
)
EXTRAORDINARY_TAB_EMPTY_MESSAGE = (
    "Pro tento audit nebylo mimořádné ověření zadáno."
)

# AUDIT-METHOD-SUPPORT-SNAPSHOT-1
METHOD_SUPPORT_PAYLOAD_VERSION = 1
METHOD_SUPPORT_SOURCE_SNAPSHOT_AT_CREATION = "snapshot-at-creation"
METHOD_SUPPORT_SOURCE_LIVE_AT_LEGACY_BACKFILL = "live-at-legacy-backfill"
METHOD_SUPPORT_SOURCE_UNAVAILABLE = "unavailable"
METHOD_SUPPORT_STATUS_AVAILABLE = "available"
METHOD_SUPPORT_STATUS_EMPTY = "empty"
METHOD_SUPPORT_STATUS_UNAVAILABLE = "unavailable"
METHOD_SUPPORT_UNAVAILABLE_MESSAGE = (
    "Metodická podpora není pro tento starší audit dostupná."
)
METHOD_SUPPORT_SECTION_KEYS: tuple[str, ...] = (
    "objektivni_dukazy",
    "doporucene_rozhovory",
    "pozorovani_v_provozu",
    "typicke_neshody",
    "pkz",
    "pozorovani",
    "vazby_procesy",
    "pozadavky_normy",
    "postup_kontroly",
    "referencni_fotografie",
    "typicke_zavady",
    "doporucene_postupy",
    "legislativa",
    "poznamky_auditora",
)
METHOD_SUPPORT_SECTION_TEXT_KEYS: tuple[str, ...] = (
    "cil_overeni",
    "popis",
)
METHOD_SUPPORT_PROCESS_KEYS: tuple[str, ...] = (
    "vazby_procesy",
    "pozadavky_norem",
)

EXTRAORDINARY_INCOMPLETE_SEVERITY_FOR_AUDIT = (
    "Mimořádná otázka „{text}“ (id={question_id}) nemá platnou závažnost. "
    "Doplňte závažnost v evidenci mimořádného ověření a audit znovu založte."
)
EXTRAORDINARY_INCOMPLETE_VERIFICATION_TYPE_FOR_AUDIT = (
    "Mimořádná otázka „{text}“ (id={question_id}) nemá platný typ ověření "
    "(Dokumentace/Terén). Doplňte typ ověření v evidenci mimořádného ověření "
    "a audit znovu založte."
)

# Stabilní technické identifikátory kategorie bez procesu (ne živá JSON metodika).
EXTRAORDINARY_CATEGORY_PROCESS_ID = "__extraordinary__"
EXTRAORDINARY_CATEGORY_PROCESS_NAME = "Mimořádná ověření"
EXTRAORDINARY_CATEGORY_SECTION_ID = "__extraordinary_section__"
EXTRAORDINARY_CATEGORY_SECTION_NAME = "Mimořádná ověření"
EXTRAORDINARY_ASSERTION_ID_PREFIX = "eq-"
EXTRAORDINARY_SNAPSHOT_ORDER_BASE = 100_000

AUDITABLE_WORKPLACE_REQUIRED_MESSAGE = (
    "Vybraná položka není aktivním auditovatelným provozem."
)
SYSTEM_AUDIT_WORKPLACE_INVALID_MESSAGE = (
    "Uložený systémový provoz není aktivním auditovatelným provozem. "
    "Vyberte platný systémový provoz."
)
SYSTEM_AUDIT_WORKPLACE_INVALID_COMBO_SUFFIX = " (neplatné nastavení)"


def extraordinary_assertion_id(question_id: int) -> str:
    return f"{EXTRAORDINARY_ASSERTION_ID_PREFIX}{int(question_id)}"


def parse_extraordinary_question_id(assertion_id: str) -> int | None:
    text = str(assertion_id or "").strip()
    prefix = EXTRAORDINARY_ASSERTION_ID_PREFIX
    if not text.startswith(prefix):
        return None
    raw = text[len(prefix) :]
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


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
