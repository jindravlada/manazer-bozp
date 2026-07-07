import re
from dataclasses import dataclass

from moduly.pravni_pozadavky.constants import (
    DOCUMENT_TYPE_NARIZENI_VLADY,
    DOCUMENT_TYPE_VYHLASKA,
    DOCUMENT_TYPE_ZAKON,
)

_NUMBER_YEAR_PATTERN = re.compile(
    r"(?P<number>\d+)\s*/\s*(?P<year>\d{4})\s*(?:Sb\.?)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BulkInternetImportLine:
    source_line: str
    document_type: str
    number: str
    year: int


def bulk_import_regulation_label(*, number: str, year: int) -> str:
    return f"{number}/{year} Sb."


def parse_bulk_import_line(line: str) -> BulkInternetImportLine:
    stripped = (line or "").strip()
    if not stripped:
        raise ValueError("Prázdný řádek.")

    match = _NUMBER_YEAR_PATTERN.search(stripped)
    if match is None:
        raise ValueError("Nepodařilo se rozpoznat číslo a rok předpisu.")

    prefix = stripped[: match.start()].strip().casefold()
    document_type = _detect_document_type(prefix)

    return BulkInternetImportLine(
        source_line=stripped,
        document_type=document_type,
        number=match.group("number"),
        year=int(match.group("year")),
    )


def _detect_document_type(prefix: str) -> str:
    if not prefix:
        return DOCUMENT_TYPE_ZAKON
    if prefix == "nv" or "nařízení vlády" in prefix:
        return DOCUMENT_TYPE_NARIZENI_VLADY
    if "vyhláška" in prefix:
        return DOCUMENT_TYPE_VYHLASKA
    if "zákon" in prefix:
        return DOCUMENT_TYPE_ZAKON
    return DOCUMENT_TYPE_ZAKON
