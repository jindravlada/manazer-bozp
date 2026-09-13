import re

from moduly.pravni_pozadavky.constants import (
    DOCUMENT_TYPE_JINY,
    DOCUMENT_TYPE_NALEZ_US,
    DOCUMENT_TYPE_NARIZENI_EU,
    DOCUMENT_TYPE_NARIZENI_VLADY,
    DOCUMENT_TYPE_SDELENI,
    DOCUMENT_TYPE_SMERNICE_EU,
    DOCUMENT_TYPE_USTAVNI_ZAKON,
    DOCUMENT_TYPE_VYHLASKA,
    DOCUMENT_TYPE_ZAKON,
    DOCUMENT_TYPE_LABELS,
    VALID_DOCUMENT_TYPES,
)

_TITLE_TYPE_RULES: tuple[tuple[str, str], ...] = (
    ("nález ústavního soudu", DOCUMENT_TYPE_NALEZ_US),
    ("ústavní zákon", DOCUMENT_TYPE_USTAVNI_ZAKON),
    ("směrnice evropské unie", DOCUMENT_TYPE_SMERNICE_EU),
    ("směrnice eu", DOCUMENT_TYPE_SMERNICE_EU),
    ("nařízení evropské unie", DOCUMENT_TYPE_NARIZENI_EU),
    ("nařízení eu", DOCUMENT_TYPE_NARIZENI_EU),
    ("nařízení vlády", DOCUMENT_TYPE_NARIZENI_VLADY),
    ("vyhláška", DOCUMENT_TYPE_VYHLASKA),
    ("sdělení", DOCUMENT_TYPE_SDELENI),
    ("zákoník", DOCUMENT_TYPE_ZAKON),
    ("zákon české národní rady", DOCUMENT_TYPE_ZAKON),
)


def normalize_document_type(value: str, *, required: bool = True) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        if required:
            raise ValueError("Typ předpisu je povinný.")
        return DOCUMENT_TYPE_ZAKON

    if normalized in VALID_DOCUMENT_TYPES:
        return normalized

    by_label = {label.lower(): key for key, label in DOCUMENT_TYPE_LABELS.items()}
    if normalized in by_label:
        return by_label[normalized]

    if required:
        raise ValueError(f"Neplatný typ předpisu: {value}")
    return DOCUMENT_TYPE_JINY


def detect_document_type_from_text(text: str) -> str:
    folded = (text or "").strip().casefold()
    if not folded:
        return DOCUMENT_TYPE_ZAKON

    for pattern, document_type in _TITLE_TYPE_RULES:
        if pattern in folded:
            return document_type

    if folded.startswith("zákon"):
        return DOCUMENT_TYPE_ZAKON

    return DOCUMENT_TYPE_JINY


def detect_document_type_from_bulk_prefix(source_line: str) -> str | None:
    stripped = (source_line or "").strip()
    if not stripped:
        return None

    match = re.search(r"(\d+)\s*/\s*(\d{4})", stripped)
    if match is None:
        return None

    prefix = stripped[: match.start()].strip().casefold()
    if not prefix:
        return None

    if prefix == "nv" or "nařízení vlády" in prefix:
        return DOCUMENT_TYPE_NARIZENI_VLADY
    if "vyhláška" in prefix:
        return DOCUMENT_TYPE_VYHLASKA
    if "ústavní zákon" in prefix:
        return DOCUMENT_TYPE_USTAVNI_ZAKON
    if "sdělení" in prefix:
        return DOCUMENT_TYPE_SDELENI
    if "nález" in prefix:
        return DOCUMENT_TYPE_NALEZ_US
    if "směrnice" in prefix:
        return DOCUMENT_TYPE_SMERNICE_EU
    if "nařízení eu" in prefix or "nařízení evropské unie" in prefix:
        return DOCUMENT_TYPE_NARIZENI_EU
    if "zákon" in prefix or "zákoník" in prefix:
        return DOCUMENT_TYPE_ZAKON

    return None


def resolve_document_type(
    *,
    explicit: str = "",
    title: str = "",
    source_line: str = "",
) -> str:
    if title.strip():
        return detect_document_type_from_text(title)

    from_prefix = detect_document_type_from_bulk_prefix(source_line)
    if from_prefix is not None:
        return from_prefix

    if explicit.strip():
        return normalize_document_type(explicit, required=False)

    return DOCUMENT_TYPE_ZAKON
