import re
from typing import NamedTuple

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
FILTER_INACTIVE_ONLY = "Neaktivní"
FILTER_ARCHIVED_ONLY = "Archivní"
FILTER_ALL_RECORDS = "Vše"

FILTER_PROCESS_LEVEL_ROOTS = "Kořenové"
FILTER_PROCESS_LEVEL_ALL = "Všechny"
FILTER_PROCESS_LEVEL_CHILDREN = "Podřízené"

DEFAULT_ACTIVE_FILTER = FILTER_ACTIVE_ONLY
DEFAULT_DOCUMENT_ACTIVE_FILTER = FILTER_ACTIVE_ONLY
DEFAULT_PROCESS_LEVEL_FILTER = FILTER_PROCESS_LEVEL_ROOTS

FILTER_INCLUDED_IN_PROCESSES_YES = "ANO"
FILTER_INCLUDED_IN_PROCESSES_NO = "NE"
DEFAULT_INCLUDED_IN_PROCESSES_FILTER = FILTER_ALL_RECORDS

DOCUMENT_TYPE_ZAKON = "zakon"
DOCUMENT_TYPE_USTAVNI_ZAKON = "ustavni_zakon"
DOCUMENT_TYPE_NARIZENI_VLADY = "narizeni_vlady"
DOCUMENT_TYPE_VYHLASKA = "vyhlaska"
DOCUMENT_TYPE_SDELENI = "sdeleni"
DOCUMENT_TYPE_NALEZ_US = "nalez_us"
DOCUMENT_TYPE_NARIZENI_EU = "narizeni_eu"
DOCUMENT_TYPE_SMERNICE_EU = "smernice_eu"
DOCUMENT_TYPE_JINY = "jiny"

VALID_DOCUMENT_TYPES = frozenset(
    {
        DOCUMENT_TYPE_ZAKON,
        DOCUMENT_TYPE_USTAVNI_ZAKON,
        DOCUMENT_TYPE_NARIZENI_VLADY,
        DOCUMENT_TYPE_VYHLASKA,
        DOCUMENT_TYPE_SDELENI,
        DOCUMENT_TYPE_NALEZ_US,
        DOCUMENT_TYPE_NARIZENI_EU,
        DOCUMENT_TYPE_SMERNICE_EU,
        DOCUMENT_TYPE_JINY,
    }
)

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    DOCUMENT_TYPE_ZAKON: "Zákon",
    DOCUMENT_TYPE_USTAVNI_ZAKON: "Ústavní zákon",
    DOCUMENT_TYPE_NARIZENI_VLADY: "Nařízení vlády",
    DOCUMENT_TYPE_VYHLASKA: "Vyhláška",
    DOCUMENT_TYPE_SDELENI: "Sdělení",
    DOCUMENT_TYPE_NALEZ_US: "Nález Ústavního soudu",
    DOCUMENT_TYPE_NARIZENI_EU: "Nařízení Evropské unie",
    DOCUMENT_TYPE_SMERNICE_EU: "Směrnice Evropské unie",
    DOCUMENT_TYPE_JINY: "Jiný předpis",
}


SECTION_PART = "cast"
SECTION_HEAD = "hlava"
SECTION_DIVISION = "dil"
SECTION_PARAGRAPH = "paragraf"
SECTION_SUBSECTION = "odstavec"
SECTION_LETTER = "pismeno"
SECTION_ATTACHMENT = "priloha"

VALID_SECTION_TYPES = frozenset(
    {
        SECTION_PART,
        SECTION_HEAD,
        SECTION_DIVISION,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
        SECTION_LETTER,
        SECTION_ATTACHMENT,
    }
)

SECTION_TYPE_LABELS: dict[str, str] = {
    SECTION_PART: "Část",
    SECTION_HEAD: "Hlava",
    SECTION_DIVISION: "Díl",
    SECTION_PARAGRAPH: "Paragraf",
    SECTION_SUBSECTION: "Odstavec",
    SECTION_LETTER: "Písmeno",
    SECTION_ATTACHMENT: "Příloha",
}


def legal_document_regulation_number(document) -> str:
    number = (getattr(document, "number", "") or "").strip()
    if "sb." in number.casefold():
        return number
    year = getattr(document, "year", None)
    if number and year is not None:
        return f"{number}/{year} Sb."
    return number


def legal_document_display_label(document) -> str:
    short_title = (getattr(document, "short_title", "") or "").strip()
    if short_title:
        return short_title
    return (getattr(document, "title", "") or "").strip()


def _strip_section_title_suffix(label: str) -> str:
    if " – " in label:
        return label.split(" – ", 1)[0].strip()
    return label.strip()


_PROCESS_CODE_RE = re.compile(r"^P-(\d+)(?:\.(\d+))?$", re.IGNORECASE)


class ProcessCodeParts(NamedTuple):
    root: int
    child: int | None = None


def format_process_code(number: int) -> str:
    return f"P-{number:03d}"


def parse_process_code(code: str) -> ProcessCodeParts | None:
    match = _PROCESS_CODE_RE.match((code or "").strip())
    if match is None:
        return None
    child_text = match.group(2)
    return ProcessCodeParts(
        root=int(match.group(1)),
        child=int(child_text) if child_text is not None else None,
    )


def is_valid_process_code(code: str) -> bool:
    return parse_process_code(code) is not None


def parse_process_code_number(code: str) -> int | None:
    parts = parse_process_code(code)
    if parts is None:
        return None
    return parts.root


def process_code_sort_key(requirement) -> tuple:
    code = (getattr(requirement, "process_code", "") or "").strip()
    parts = parse_process_code(code)
    if parts is not None:
        return (0, parts.root, parts.child or 0)
    return (1, code.lower())


def legal_requirement_merged_target_label(target) -> str:
    code = (getattr(target, "process_code", "") or "").strip()
    title = legal_requirement_process_label(target)
    if code and title:
        return f"{code} – {title}"
    if code:
        return code
    if title:
        return title
    return f"Proces #{getattr(target, 'id', '')}"


def legal_requirement_regulation_label(requirement) -> str:
    number = (getattr(requirement, "regulation_number", "") or "").strip()
    if number:
        return number
    return (getattr(requirement, "regulation_name", "") or "").strip()


def legal_requirement_process_label(requirement) -> str:
    title = (getattr(requirement, "title", "") or "").strip()
    if title:
        return title
    return (getattr(requirement, "regulation_name", "") or "").strip()


def legal_requirement_responsible_label(requirement) -> str:
    parts: list[str] = []
    person_name = (getattr(requirement, "responsible_person_name", "") or "").strip()
    role_name = (getattr(requirement, "responsible_role_name", "") or "").strip()
    if person_name:
        parts.append(person_name)
    if role_name:
        parts.append(role_name)
    return " / ".join(parts)


def legal_requirement_provision_label(
    requirement,
    *,
    section=None,
    sections_by_id: dict | None = None,
) -> str:
    if section is not None:
        return legal_section_provision_label(section, sections_by_id=sections_by_id)

    provision = (getattr(requirement, "provision", "") or "").strip()
    if provision.startswith("§"):
        return _strip_section_title_suffix(provision)
    return provision


def legal_section_provision_label(section, *, sections_by_id: dict | None = None) -> str:
    paragraph = ""
    subsection = ""
    letter = ""

    current = section
    visited: set[int] = set()
    while current is not None and current.id not in visited:
        visited.add(current.id)
        section_type = (getattr(current, "section_type", "") or "").strip()
        if section_type == SECTION_LETTER:
            letter = (getattr(current, "item_letter", "") or "").strip()
        elif section_type == SECTION_SUBSECTION:
            subsection = (getattr(current, "section_number", "") or "").strip()
        elif section_type == SECTION_PARAGRAPH:
            paragraph = (getattr(current, "paragraph", "") or "").strip()
        else:
            paragraph_value = (getattr(current, "paragraph", "") or "").strip()
            if paragraph_value:
                paragraph = paragraph_value

        parent_id = getattr(current, "parent_section_id", None)
        if parent_id is None:
            break
        if sections_by_id is not None:
            current = sections_by_id.get(parent_id)
        else:
            current = None

    parts: list[str] = []
    if paragraph:
        parts.append(f"§ {paragraph}")
    if subsection:
        parts.append(f"odst. {subsection}")
    if letter:
        parts.append(f"písm. {letter})")
    if parts:
        return " ".join(parts)

    return _strip_section_title_suffix(legal_section_display_label(section))


def legal_requirement_source_display_label(
    document,
    section,
    *,
    sections_by_id: dict | None = None,
) -> str:
    document_label = ""
    if document is not None:
        title = (getattr(document, "title", "") or "").strip()
        document_label = title or legal_document_regulation_number(document)

    provision = legal_section_provision_label(section, sections_by_id=sections_by_id)
    if document_label and provision:
        return f"{document_label} – {provision}"
    if provision:
        return provision
    return document_label


def legal_section_display_label(section) -> str:
    paragraph = (getattr(section, "paragraph", "") or "").strip()
    section_number = (getattr(section, "section_number", "") or "").strip()
    item_letter = (getattr(section, "item_letter", "") or "").strip()
    title = (getattr(section, "title", "") or "").strip()
    section_type = (getattr(section, "section_type", "") or "").strip()

    if section_type == SECTION_ATTACHMENT:
        if title:
            return title
        if section_number:
            return f"Příloha č. {section_number}"
        return "Příloha"

    parts: list[str] = []
    if paragraph:
        parts.append(f"§ {paragraph}")
    if section_number:
        if section_type == SECTION_SUBSECTION:
            parts.append(f"odst. {section_number}")
        else:
            parts.append(section_number)
    if item_letter:
        parts.append(f"písm. {item_letter})")

    if title:
        if parts:
            return f"{' '.join(parts)} – {title}"
        return title
    if parts:
        return " ".join(parts)

    type_label = SECTION_TYPE_LABELS.get(section_type, section_type)
    section_id = getattr(section, "id", None)
    if type_label:
        return type_label
    return f"Ustanovení #{section_id}" if section_id is not None else ""


CHANGE_NEW = "new"
CHANGE_UPDATED = "updated"
CHANGE_REPEALED = "repealed"
CHANGE_OTHER = "other"
CHANGE_NOVELIZATION = "novelization"
NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX = "esbirka-ref:"

VALID_CHANGE_TYPES = frozenset(
    {
        CHANGE_NEW,
        CHANGE_UPDATED,
        CHANGE_REPEALED,
        CHANGE_OTHER,
        CHANGE_NOVELIZATION,
    }
)

CHANGE_TYPE_LABELS: dict[str, str] = {
    CHANGE_NEW: "Nový předpis / ustanovení",
    CHANGE_UPDATED: "Změna",
    CHANGE_REPEALED: "Zrušení",
    CHANGE_OTHER: "Jiné",
    CHANGE_NOVELIZATION: "Novelizace předpisu",
}


CHECK_RUN_NEW = "new"
CHECK_RUN_IN_PROGRESS = "in_progress"
CHECK_RUN_COMPLETED = "completed"
CHECK_RUN_ERROR = "error"
CHECK_RUN_CANCELLED = "cancelled"

VALID_CHECK_RUN_STATUSES = frozenset(
    {
        CHECK_RUN_NEW,
        CHECK_RUN_IN_PROGRESS,
        CHECK_RUN_COMPLETED,
        CHECK_RUN_ERROR,
        CHECK_RUN_CANCELLED,
    }
)

CHECK_RUN_STATUS_LABELS: dict[str, str] = {
    CHECK_RUN_NEW: "Připravena",
    CHECK_RUN_IN_PROGRESS: "Probíhá",
    CHECK_RUN_COMPLETED: "Dokončená",
    CHECK_RUN_ERROR: "Chyba",
    CHECK_RUN_CANCELLED: "Zrušená",
}

CHECK_RUN_CRASH_RECOVERY_MESSAGE = (
    "Kontrola nebyla dokončena – pravděpodobně došlo k ukončení programu během kontroly."
)

DEFAULT_CHECK_RUN_STATUS = CHECK_RUN_NEW

PROCESSING_NEW = "new"
PROCESSING_AI_PROPOSED = "ai_proposed"
PROCESSING_REVIEWED = "reviewed"
PROCESSING_APPROVED = "approved"
PROCESSING_ARCHIVED = "archived"

VALID_PROCESSING_STATUSES = frozenset(
    {
        PROCESSING_NEW,
        PROCESSING_AI_PROPOSED,
        PROCESSING_REVIEWED,
        PROCESSING_APPROVED,
        PROCESSING_ARCHIVED,
    }
)

PROCESSING_STATUS_LABELS: dict[str, str] = {
    PROCESSING_NEW: "Nový",
    PROCESSING_AI_PROPOSED: "Návrh AI",
    PROCESSING_REVIEWED: "Zkontrolováno",
    PROCESSING_APPROVED: "Schváleno",
    PROCESSING_ARCHIVED: "Archivováno",
}

DEFAULT_PROCESSING_STATUS = PROCESSING_NEW

REQUIREMENT_STATUS_NONE = "none"
REQUIREMENT_STATUS_EXISTS = "exists"
REQUIREMENT_STATUS_APPROVED = "approved"

REQUIREMENT_TREE_ICON_NONE = "○"
REQUIREMENT_TREE_ICON_EXISTS = "●"
REQUIREMENT_TREE_ICON_APPROVED = "✔"

