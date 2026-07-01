"""Metadata a konstanty modulu Audity ISO 45001."""

from dataclasses import dataclass

MODULE_KEY = "audity"
MODULE_NAME = "Audity ISO 45001"
MODULE_DESCRIPTION = "Evidence interních auditů systému řízení BOZP."

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

TAB_AUDITOVANE_PROCESY = "Auditované procesy"

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

TAB_LABELS = (
    "Spis",
    "Komise",
    TAB_AUDITOVANE_PROCESY,
    "Zjištění",
    "Úkoly",
    "Závěr",
)

PROCESS_PANEL_LEFT_WIDTH = 260
PROCESS_NOT_IMPLEMENTED_TEXT = "Tento auditovaný proces zatím není implementován."
PROCESS_PART_NOT_IMPLEMENTED_TEXT = "Tato část bude doplněna."

FINDING_SOURCE_LABEL = "Audit ISO 45001"
FINDING_DIALOG_TITLE = "Zjištění auditu"
FINDING_CREATE_FROM_CONTROL_POINT_LABEL = "➕ Založit zjištění"
FINDING_OPEN_EXISTING_LABEL = "Otevřít zjištění"
FINDING_CREATED_LABEL = "Zjištění založeno"
FINDING_DUPLICATE_MESSAGE = "Pro tuto auditní otázku už existuje zjištění. Otevře se existující záznam."
AUDIT_MUST_BE_SAVED_MESSAGE = "Audit je nutné nejdříve uložit."
FINDING_REQUIRES_NONCOMPLIANCE_MESSAGE = (
    "Zjištění lze založit pouze u auditní otázky s výsledkem „Nevyhovuje“."
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

PROCESS_TERM_PROCESS = "Auditovaný proces"
PROCESS_TERM_CRITERION = "Kritérium"
PROCESS_TERM_QUESTION = "Auditní otázka"

CONTROL_POINT_HISTORY_EMPTY = "Zatím bez historie."
CONTROL_POINT_HISTORY_SELECT = "Vyberte auditní otázku vlevo."
CONTROL_POINT_HISTORY_LIMIT = 5
CONTROL_POINT_HISTORY_WORKPLACE_TITLE = "Historie tohoto auditovaného provozu"
CONTROL_POINT_SHARED_EXPERIENCES_TITLE = "Sdílené zkušenosti"
CONTROL_POINT_HISTORY_WORKPLACE_NO_WORKPLACE = "Pro zobrazení historie vyberte auditovaný provoz."
CONTROL_POINT_SHARED_EXPERIENCES_EMPTY = "Zatím bez sdílených zkušeností."


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
