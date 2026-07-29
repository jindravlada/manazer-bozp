import re
from dataclasses import dataclass

from moduly.pravni_pozadavky.legal_document_type_utils import (
    detect_document_type_from_bulk_prefix,
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

    document_type = detect_document_type_from_bulk_prefix(stripped)
    if document_type is None:
        from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_ZAKON

        document_type = DOCUMENT_TYPE_ZAKON

    return BulkInternetImportLine(
        source_line=stripped,
        document_type=document_type,
        number=match.group("number"),
        year=int(match.group("year")),
    )
