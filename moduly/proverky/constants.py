"""Metadata a konstanty modulu Prověrky BOZP."""

from dataclasses import dataclass

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

TAB_KONTROLOVANE_OBLASTI = "Kontrolované oblasti"

TAB_LABELS = (
    "Spis",
    "Komise",
    TAB_KONTROLOVANE_OBLASTI,
    "Zjištění",
    "Úkoly",
    "Přílohy",
    "Závěr",
)


@dataclass(frozen=True)
class InspectionArea:
    code: str
    name: str
    description: str


INSPECTION_AREAS: tuple[InspectionArea, ...] = (
    InspectionArea(
        "bozp",
        "BOZP obecně",
        "Obecné požadavky na bezpečnost a ochranu zdraví při práci na pracovišti.",
    ),
    InspectionArea(
        "po",
        "Požární ochrana",
        "Prevence požárů, požární technika, evakuační cesty a organizace PO.",
    ),
    InspectionArea(
        "oopp",
        "OOPP",
        "Osobní ochranné pracovní prostředky — dostupnost, používání a evidence.",
    ),
    InspectionArea(
        "dokumentace",
        "Dokumentace",
        "Bezpečnostní dokumentace, posudky, směrnice a provozní předpisy.",
    ),
    InspectionArea(
        "revize",
        "Revize a kontroly",
        "Platnost revizí, pravidelné kontroly technických zařízení a záznamy o nich.",
    ),
    InspectionArea(
        "doprava",
        "Doprava a manipulace",
        "Vnitřní doprava, skladování, zdvihací zařízení a manipulace s břemeny.",
    ),
    InspectionArea(
        "dodavatele",
        "Dodavatelé",
        "Práce dodavatelů na pracovišti, koordinace BOZP a plnění povinností.",
    ),
    InspectionArea(
        "rizikova_pracoviste",
        "Riziková pracoviště",
        "Práce ve výškách, v hloubce, s nebezpečnými látkami a další zvýšená rizika.",
    ),
    InspectionArea(
        "chemie",
        "Chemické látky",
        "Skladování, označování, manipulace a evidence nebezpečných chemických látek.",
    ),
    InspectionArea(
        "prvni_pomoc",
        "První pomoc",
        "Lékárničky, vyškolení osoby pro první pomoc a vybavení pro ošetření.",
    ),
)

AREA_PANEL_LEFT_WIDTH = 260
AREA_NOT_IMPLEMENTED_TEXT = "Tato oblast zatím není implementována."
AREA_PART_NOT_IMPLEMENTED_TEXT = "Tato část bude doplněna."

AREA_CODE_PRVNI_POMOC = "prvni_pomoc"

FIRST_AID_PARTS = (
    "Lékárnička",
    "Oční sprcha",
    "Školené osoby",
    "Telefonní čísla",
)
