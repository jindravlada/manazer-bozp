COMPLIANCE_SPLNENO = "splneno"
COMPLIANCE_CASTECNE_SPLNENO = "castecne_splneno"
COMPLIANCE_NESPLNENO = "nesplneno"
COMPLIANCE_NENI_RELEVANTNI = "neni_relevantni"

VALID_COMPLIANCE_STATUSES = frozenset(
    {
        COMPLIANCE_SPLNENO,
        COMPLIANCE_CASTECNE_SPLNENO,
        COMPLIANCE_NESPLNENO,
        COMPLIANCE_NENI_RELEVANTNI,
    }
)

COMPLIANCE_STATUS_LABELS: dict[str, str] = {
    COMPLIANCE_SPLNENO: "Splněno",
    COMPLIANCE_CASTECNE_SPLNENO: "Částečně splněno",
    COMPLIANCE_NESPLNENO: "Nesplněno",
    COMPLIANCE_NENI_RELEVANTNI: "Není relevantní",
}

PERIODICITY_MESICNE = "mesicne"
PERIODICITY_CTVRTLETNE = "ctvrtletne"
PERIODICITY_POLOLETNE = "pololetne"
PERIODICITY_ROCNE = "rocne"
PERIODICITY_DVA_ROKY = "dva_roky"
PERIODICITY_TRI_ROKY = "tri_roky"
PERIODICITY_NA_POZADANI = "na_pozadani"
PERIODICITY_BEZ = "bez_periodicity"

DEFAULT_SANCTION_CURRENCY = "Kč"

VALID_PERIODICITIES = frozenset(
    {
        PERIODICITY_MESICNE,
        PERIODICITY_CTVRTLETNE,
        PERIODICITY_POLOLETNE,
        PERIODICITY_ROCNE,
        PERIODICITY_DVA_ROKY,
        PERIODICITY_TRI_ROKY,
        PERIODICITY_NA_POZADANI,
        PERIODICITY_BEZ,
    }
)

PERIODICITY_LABELS: dict[str, str] = {
    PERIODICITY_MESICNE: "Měsíčně",
    PERIODICITY_CTVRTLETNE: "Čtvrtletně",
    PERIODICITY_POLOLETNE: "Pololetně",
    PERIODICITY_ROCNE: "Ročně",
    PERIODICITY_DVA_ROKY: "Každé 2 roky",
    PERIODICITY_TRI_ROKY: "Každé 3 roky",
    PERIODICITY_NA_POZADANI: "Na vyžádání",
    PERIODICITY_BEZ: "Bez periodicity",
}

PERIODICITY_MONTHS: dict[str, int] = {
    PERIODICITY_MESICNE: 1,
    PERIODICITY_CTVRTLETNE: 3,
    PERIODICITY_POLOLETNE: 6,
    PERIODICITY_ROCNE: 12,
    PERIODICITY_DVA_ROKY: 24,
    PERIODICITY_TRI_ROKY: 36,
}

FILTER_AREA_VSE = "Vše"
FILTER_STATUS_VSE = "Vše"
FILTER_PERSON_VSE = "Vše"
FILTER_ACTIVE_ONLY = "Aktivní"
FILTER_ARCHIVED_ONLY = "Archivní"
FILTER_ALL_RECORDS = "Vše"

DEFAULT_ACTIVE_FILTER = FILTER_ACTIVE_ONLY

DOCUMENT_TYPE_ZAKON = "zakon"
DOCUMENT_TYPE_NARIZENI_VLADY = "narizeni_vlady"
DOCUMENT_TYPE_VYHLASKA = "vyhlaska"
DOCUMENT_TYPE_SMERNICE_EU = "smernice_eu"
DOCUMENT_TYPE_JINY = "jiny"

VALID_DOCUMENT_TYPES = frozenset(
    {
        DOCUMENT_TYPE_ZAKON,
        DOCUMENT_TYPE_NARIZENI_VLADY,
        DOCUMENT_TYPE_VYHLASKA,
        DOCUMENT_TYPE_SMERNICE_EU,
        DOCUMENT_TYPE_JINY,
    }
)

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    DOCUMENT_TYPE_ZAKON: "Zákon",
    DOCUMENT_TYPE_NARIZENI_VLADY: "Nařízení vlády",
    DOCUMENT_TYPE_VYHLASKA: "Vyhláška",
    DOCUMENT_TYPE_SMERNICE_EU: "Směrnice EU",
    DOCUMENT_TYPE_JINY: "Jiný předpis",
}


SECTION_PART = "cast"
SECTION_HEAD = "hlava"
SECTION_DIVISION = "dil"
SECTION_PARAGRAPH = "paragraf"
SECTION_SUBSECTION = "odstavec"
SECTION_LETTER = "pismeno"

VALID_SECTION_TYPES = frozenset(
    {
        SECTION_PART,
        SECTION_HEAD,
        SECTION_DIVISION,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
        SECTION_LETTER,
    }
)

SECTION_TYPE_LABELS: dict[str, str] = {
    SECTION_PART: "Část",
    SECTION_HEAD: "Hlava",
    SECTION_DIVISION: "Díl",
    SECTION_PARAGRAPH: "Paragraf",
    SECTION_SUBSECTION: "Odstavec",
    SECTION_LETTER: "Písmeno",
}


def legal_document_display_label(document) -> str:
    short_title = (getattr(document, "short_title", "") or "").strip()
    if short_title:
        return short_title
    return (getattr(document, "title", "") or "").strip()

