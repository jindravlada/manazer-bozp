"""Metadata a konstanty modulu Prověrky BOZP."""

from dataclasses import dataclass

from core.shared.verification_type import (
    VERIFICATION_TYPE_DEFAULT,
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_LABELS,
    VERIFICATION_TYPE_OPTIONS,
    VERIFICATION_TYPE_TERRAIN,
)

MODULE_KEY = "proverky"
MODULE_NAME = "Prověrky BOZP"
MODULE_DESCRIPTION = "Roční prověrky BOZP/PO na pracovištích."

INSPECTION_STATUS_PLANOVANO = "Plánováno"
INSPECTION_STATUS_PROBIHA = "Probíhá"
INSPECTION_STATUS_DOKONCENO = "Dokončeno"

INSPECTION_SPIS_STATUSES = (
    INSPECTION_STATUS_PLANOVANO,
    INSPECTION_STATUS_PROBIHA,
    INSPECTION_STATUS_DOKONCENO,
)

DEFAULT_INSPECTION_SPIS_STATUS = INSPECTION_STATUS_PLANOVANO

INSPECTION_COMPLETION_CONFIRM_MESSAGE = (
    "Prověrka obsahuje otevřená zjištění nebo aktivní úkoly. "
    "Přesto ji chcete označit jako dokončenou?"
)

INSPECTION_TYPE_RADNA = "Řádná"
INSPECTION_TYPE_MIMORADNA = "Mimořádná"

INSPECTION_TYPES = (
    INSPECTION_TYPE_RADNA,
    INSPECTION_TYPE_MIMORADNA,
)

DEFAULT_INSPECTION_TYPE = INSPECTION_TYPE_RADNA

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
INSPECTION_STATUS_PLANOVANA = INSPECTION_STATUS_PLANOVANO
INSPECTION_STATUS_DOKONCENA = INSPECTION_STATUS_DOKONCENO
INSPECTION_STATUS_UZAVRENA = INSPECTION_STATUS_DOKONCENO
DEFAULT_INSPECTION_STATUS = DEFAULT_INSPECTION_SPIS_STATUS

VALID_INSPECTION_STATUSES = frozenset(INSPECTION_SPIS_STATUSES)

INSPECTION_STATUS_FILTER_PROBIHAJICI = "Probíhající"
INSPECTION_STATUS_FILTER_PLANOVANE = "Plánované"
INSPECTION_STATUS_FILTER_DOKONCENE = "Dokončené"
INSPECTION_STATUS_FILTER_VSE = "Vše"

DEFAULT_INSPECTION_STATUS_FILTER = INSPECTION_STATUS_FILTER_PROBIHAJICI

INSPECTION_STATUS_BY_FILTER = {
    INSPECTION_STATUS_FILTER_PROBIHAJICI: INSPECTION_STATUS_PROBIHA,
    INSPECTION_STATUS_FILTER_PLANOVANE: INSPECTION_STATUS_PLANOVANO,
    INSPECTION_STATUS_FILTER_DOKONCENE: INSPECTION_STATUS_DOKONCENO,
}

YEAR_FILTER_VSE = "Vše"

ROCNI_ZPRAVA_TOOLTIP = "Bude dostupné po dokončení statistik a ročních přehledů."

TAB_KONTROLOVANE_OBLASTI = "Kontrolované oblasti"
TAB_TEREN = "Terén"

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

COMMISSION_MISSING_LEADER_MESSAGE = "Vyberte vedoucího komise z THP pracovníků."
COMMISSION_MISSING_WORKPLACE_MESSAGE = "Vyberte zástupce pracoviště z THP pracovníků."
COMMISSION_MISSING_UNION_MESSAGE = "Vyberte zástupce odborové organizace ze seznamu osob."

COMMISSION_DEFAULT_ROLE_MEMBER = "Člen komise"
COMMISSION_DEFAULT_ROLE_INVITED = "Přizvaná osoba"
COMMISSION_DUPLICATE_PERSON_MESSAGE = "Tato osoba je již v komisi zařazena."

TAB_LABELS = (
    "Spis",
    "Komise",
    TAB_KONTROLOVANE_OBLASTI,
    TAB_TEREN,
    "Zjištění",
    "Úkoly",
    "Závěr",
)

AREA_PANEL_LEFT_WIDTH = 260
AREA_NOT_IMPLEMENTED_TEXT = "Tato oblast zatím není implementována."
AREA_PART_NOT_IMPLEMENTED_TEXT = "Tato část bude doplněna."
AREA_PART_NO_CONTROL_QUESTIONS_TEXT = (
    "Pro tuto část nejsou evidovány žádné kontrolní otázky."
)
CONTROL_POINTS_EMPTY_CURRENT_PART = (
    "V této části nejsou evidovány žádné kontrolní body."
)
CONTROL_POINTS_EMPTY_SEE_DOCUMENTATION = (
    "Kontrola této oblasti probíhá v části Dokumentace."
)
CONTROL_POINTS_EMPTY_SEE_TERRAIN = (
    "Kontrola této oblasti probíhá v části Terén."
)
CONTROL_POINTS_EMPTY_AREA_NONE = (
    "Pro tuto oblast zatím nejsou vytvořeny žádné kontrolní body."
)
KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT = "Tato část bude doplněna."

FINDING_SOURCE_LABEL = "Prověrka BOZP"
FINDING_DIALOG_TITLE = "Zjištění prověrky BOZP"
FINDING_CREATE_FROM_CONTROL_POINT_LABEL = "➕ Založit zjištění"
FINDING_OPEN_EXISTING_LABEL = "Otevřít zjištění"
FINDING_CREATED_LABEL = "Zjištění založeno"
FINDING_DUPLICATE_MESSAGE = "Pro tento kontrolní bod už existuje zjištění. Otevře se existující záznam."
INSPECTION_MUST_BE_SAVED_MESSAGE = "Prověrku je nutné nejdříve uložit."
FINDING_REQUIRES_NONCOMPLIANCE_MESSAGE = "Zjištění lze založit pouze u kontrolního bodu s výsledkem „Nevyhovuje“."
FINDING_REQUIRES_RESULT_MESSAGE = (
    "Zjištění lze založit pouze u kontrolního bodu s výsledkem "
    "„Nevyhovuje“ nebo „Vyhovuje s doporučením“."
)

INSPECTION_PROTOCOL_BUTTON_LABEL = "Zpráva z prověrky BOZP"
INSPECTION_PROTOCOL_DIALOG_TITLE = "Zpráva z prověrky BOZP"
INSPECTION_DETAILED_REPORT_BUTTON_LABEL = "Podrobná zpráva z prověrky BOZP"
INSPECTION_DETAILED_REPORT_DIALOG_TITLE = "Podrobná zpráva z prověrky BOZP"
INSPECTION_PROTOCOL_TOOLTIP = (
    "Export zprávy je dostupný pouze pro dokončené prověrky."
)
INSPECTION_DETAILED_REPORT_TOOLTIP = (
    "Podrobná zpráva je dostupná pouze pro dokončené prověrky."
)
INSPECTION_PROTOCOL_REQUIRES_COMPLETED = (
    "Zprávu lze exportovat pouze u dokončené prověrky."
)
INSPECTION_DETAILED_REPORT_REQUIRES_COMPLETED = (
    "Podrobnou zprávu lze exportovat pouze u dokončené prověrky."
)
INSPECTION_INVALID_DATE_ORDER_MESSAGE = (
    "Datum ukončení nesmí být dříve než datum zahájení."
)

CONTROL_POINT_HISTORY_EMPTY = "Zatím bez historie."
CONTROL_POINT_HISTORY_SELECT = "Vyberte kontrolní bod vlevo."
CONTROL_POINT_HISTORY_LIMIT = 5
CONTROL_POINT_HISTORY_WORKPLACE_TITLE = "Historie tohoto pracoviště"
CONTROL_POINT_SHARED_EXPERIENCES_TITLE = "Sdílené zkušenosti"
CONTROL_POINT_HISTORY_WORKPLACE_NO_WORKPLACE = "Pro zobrazení historie vyberte pracoviště."
CONTROL_POINT_SHARED_EXPERIENCES_EMPTY = "Zatím bez sdílených zkušeností."

KNOWLEDGE_EDITOR_BUTTON_LABEL = "Editor znalostí"
KNOWLEDGE_EDITOR_WINDOW_TITLE = "Editor znalostí prověrek"
KNOWLEDGE_EDITOR_USER_COPY_HINT = (
    "Upravujete uživatelskou kopii metodiky v "
    "~/.local/share/manazer-bozp/ciselniky/proverky/."
)
KNOWLEDGE_EDITOR_SELECT_SECTION_HINT = (
    "Vyberte oblast nebo sekci metodiky ve stromu vlevo."
)
KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_LABEL = "Řídicí proces:"
KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_EMPTY = "—"
KNOWLEDGE_EDIT_FROM_CARD_LABEL = "✏ Upravit znalosti"
KNOWLEDGE_POSTUP_KONTROLY_TITLE = "Postup kontroly"
KNOWLEDGE_CONTROL_PROCEDURE_BUTTON_LABEL = "📋 Doporučený postup kontroly"
KNOWLEDGE_CONTROL_PROCEDURE_DIALOG_TITLE = "📋 Doporučený postup kontroly"
KNOWLEDGE_REFERENCE_PHOTOS_TITLE = "📷 Referenční fotografie"
REFERENCE_PHOTO_THUMBNAIL_SIZE = 120
REFERENCE_PHOTO_PLACEHOLDER_WIDTH = 220
REFERENCE_PHOTO_PLACEHOLDER_ICON_SIZE_PX = 40
REFERENCE_PHOTO_FILTER = "Obrázky (*.jpg *.jpeg *.png *.webp *.heic *.heif);;Všechny soubory (*.*)"
KNOWLEDGE_EDITOR_DEFAULT_AREA_ID = "prvni_pomoc"
KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID = "lekarnicka"

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

MOVE_TO_TERRAIN_LABEL = "→ Terén"
MOVE_TO_DOCUMENTATION_LABEL = "→ Dokumentace"
MOVE_VERIFICATION_TYPE_TOOLTIP = (
    "Změní typ ověření jen pro tuto prověrku. Metodika zůstane beze změny."
)

TERRAIN_CHECKLIST_BUTTON_LABEL = "Vytisknout terénní checklist"
TERRAIN_CHECKLIST_DIALOG_TITLE = "Terénní checklist"
TERRAIN_CHECKLIST_TOOLTIP = (
    "Pracovní checklist kontrolních bodů pro ověření v provozu."
)
TERRAIN_CHECKLIST_SAVE_FIRST_TOOLTIP = "Nejdříve uložte prověrku."
TERRAIN_CHECKLIST_NO_TERRAIN_POINTS_TOOLTIP = (
    "Prověrka neobsahuje žádné terénní kontrolní body."
)
TERRAIN_CHECKLIST_EMPTY = "Nejsou žádné kontrolní body typu Terén."
TERRAIN_TAB_EMPTY = "Žádné kontrolní body pro terénní ověření."
TERRAIN_TAB_HINT = (
    "Kontrolní body určené k ověření v provozu. "
    "Po pochůzce doplňte hodnocení, poznámku a případně fotografie."
)
TERRAIN_CHECKLIST_REQUIRES_SAVED = "Prověrku je nutné nejdříve uložit."


@dataclass(frozen=True)
class ProverkyFindingKnowledgeContext:
    area_id: str
    area_label: str
    section_id: str
    section_label: str
    control_point_id: str
    control_point_label: str
