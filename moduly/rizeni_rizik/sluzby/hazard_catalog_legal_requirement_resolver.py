"""Vyhledání právního předpisu pro AI návrh právní vazby (R19b)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from moduly.pravni_pozadavky.constants import (
    DOCUMENT_TYPE_NARIZENI_VLADY,
    DOCUMENT_TYPE_VYHLASKA,
    DOCUMENT_TYPE_ZAKON,
    legal_document_catalog_link_label,
    legal_document_regulation_number,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
    is_similar_text_match,
    normalize_match_text,
)

REGULATION_TYPE_GOVERNMENT = DOCUMENT_TYPE_NARIZENI_VLADY
REGULATION_TYPE_DECREE = DOCUMENT_TYPE_VYHLASKA
REGULATION_TYPE_ACT = DOCUMENT_TYPE_ZAKON

_CURRENT_WORDING_RE = re.compile(
    r"\bv\s+aktuálním\s+znění\b",
    re.IGNORECASE,
)
_NUMBER_YEAR_RE = re.compile(r"(?<!\d)(\d{1,4})\s*/\s*(\d{4})(?!\d)")
_CITATION_RE = re.compile(
    r"(?P<type>"
    r"nařízení\s+vlády|"
    r"nv|"
    r"vyhláška|"
    r"vyhl|"
    r"zákoník\s+práce|"
    r"zákon|"
    r"zák"
    r")"
    r"(?:\s*č\.?)?"
    r"\s*(?P<number>\d{1,4})\s*/\s*(?P<year>\d{4})",
    re.IGNORECASE,
)


class LegalDocumentMatchKind(str, Enum):
    EXACT = "exact"
    AMBIGUOUS = "ambiguous"
    NONE = "none"


# Zpětná kompatibilita pro starší importy (R19–R20b.1).
LegalRequirementMatchKind = LegalDocumentMatchKind


@dataclass(frozen=True)
class LegalDocumentMatchResult:
    kind: LegalDocumentMatchKind
    document_id: int | None = None
    candidates: tuple[tuple[int, str], ...] = ()

    @property
    def requirement_id(self) -> int | None:
        """Deprecated alias — dříve ID požadavku, nyní ID předpisu."""
        return self.document_id


# Alias pro starší importy.
LegalRequirementMatchResult = LegalDocumentMatchResult


@dataclass(frozen=True)
class ParsedLegalCitation:
    regulation_type: str | None
    number: str
    year: str

    @property
    def number_year_key(self) -> str:
        return f"{self.number}/{self.year}"


def expand_legal_abbreviations(text: str) -> str:
    """Rozšíří běžné zkratky právních odkazů na plné tvary."""
    value = " ".join((text or "").strip().split())
    if not value:
        return ""

    value = _CURRENT_WORDING_RE.sub(" ", value)
    replacements = (
        (r"\bNV\.?\s*č\.?\s*", "Nařízení vlády "),
        (r"\bNV\.?\s+", "Nařízení vlády "),
        (r"\bvyhl\.?\s*č\.?\s*", "Vyhláška "),
        (r"\bvyhl\.?\s+", "Vyhláška "),
        (r"\bzák\.?\s*č\.?\s*", "Zákon "),
        (r"\bzák\.?\s+", "Zákon "),
    )
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    return " ".join(value.split())


def normalize_legal_citation_text(text: str) -> str:
    """
    Normalizace pro porovnání právních odkazů:
    zkratky, velikost písmen, mezery, tečky, „č.“, „v aktuálním znění“.
    """
    expanded = expand_legal_abbreviations(text)
    normalized = normalize_match_text(expanded)
    if not normalized:
        return ""
    normalized = normalized.replace("č.", " ").replace("č", " ")
    normalized = normalized.replace(".", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def parse_legal_citation(text: str) -> ParsedLegalCitation | None:
    expanded = expand_legal_abbreviations(text)
    match = _CITATION_RE.search(expanded)
    if match is not None:
        return ParsedLegalCitation(
            regulation_type=_type_token_to_key(match.group("type").casefold()),
            number=str(int(match.group("number"))),
            year=match.group("year"),
        )

    number_year = _NUMBER_YEAR_RE.search(expanded)
    if number_year is None:
        return None
    return ParsedLegalCitation(
        regulation_type=_infer_regulation_type(expanded),
        number=str(int(number_year.group(1))),
        year=number_year.group(2),
    )


def _type_token_to_key(token: str) -> str | None:
    normalized = " ".join(token.split())
    if normalized in {"nv", "nařízení vlády"}:
        return REGULATION_TYPE_GOVERNMENT
    if normalized in {"vyhl", "vyhláška"}:
        return REGULATION_TYPE_DECREE
    if normalized in {"zák", "zákon", "zákoník práce"}:
        return REGULATION_TYPE_ACT
    return None


def _infer_regulation_type(text: str) -> str | None:
    normalized = normalize_legal_citation_text(text)
    if "nařízení vlády" in normalized:
        return REGULATION_TYPE_GOVERNMENT
    if "vyhláška" in normalized:
        return REGULATION_TYPE_DECREE
    if "zákon" in normalized or "zákoník práce" in normalized:
        return REGULATION_TYPE_ACT
    return None


def _document_number_year(document) -> tuple[str | None, str | None]:
    raw_number = (getattr(document, "number", "") or "").strip()
    year_value = getattr(document, "year", None)
    year = str(year_value) if year_value is not None else None

    number_year = _NUMBER_YEAR_RE.search(raw_number)
    if number_year is not None:
        return str(int(number_year.group(1))), number_year.group(2)

    digits = re.sub(r"\D", "", raw_number)
    if digits:
        try:
            return str(int(digits)), year
        except ValueError:
            pass
    return None, year


class HazardCatalogLegalDocumentResolver:
    def resolve(self, query: str) -> LegalDocumentMatchResult:
        raw_query = (query or "").strip()
        if not raw_query:
            return LegalDocumentMatchResult(kind=LegalDocumentMatchKind.NONE)

        documents = legal_document_service.list_all(include_inactive=False)
        citation = parse_legal_citation(raw_query)
        if citation is not None:
            citation_matches = self._match_by_citation(documents, citation)
            result = self._result_from_matches(citation_matches)
            if result.kind != LegalDocumentMatchKind.NONE:
                return result

        by_code = legal_requirement_service.get_by_process_code(raw_query, active_only=True)
        if by_code is not None and by_code.legal_document_id is not None:
            document = legal_document_service.get_by_id(by_code.legal_document_id)
            if document is not None and document.active:
                return LegalDocumentMatchResult(
                    kind=LegalDocumentMatchKind.EXACT,
                    document_id=document.id,
                    candidates=((document.id, legal_document_catalog_link_label(document)),),
                )

        normalized_query = normalize_legal_citation_text(raw_query)
        if not normalized_query:
            return LegalDocumentMatchResult(kind=LegalDocumentMatchKind.NONE)

        exact_matches: list[tuple[int, str]] = []
        similar_matches: list[tuple[int, str]] = []
        for document in documents:
            label = legal_document_catalog_link_label(document)
            fields = self._candidate_fields(document)
            if any(
                normalize_legal_citation_text(field) == normalized_query
                for field in fields
                if field
            ):
                exact_matches.append((document.id, label))
                continue
            if any(
                is_similar_text_match(
                    expand_legal_abbreviations(raw_query),
                    field,
                )
                for field in fields
                if field
            ):
                similar_matches.append((document.id, label))

        exact_result = self._result_from_matches(exact_matches)
        if exact_result.kind != LegalDocumentMatchKind.NONE:
            return exact_result
        return self._result_from_matches(similar_matches)

    def _match_by_citation(
        self,
        documents,
        citation: ParsedLegalCitation,
    ) -> list[tuple[int, str]]:
        matches: list[tuple[int, str]] = []
        for document in documents:
            if not self._document_matches_citation(document, citation):
                continue
            matches.append((document.id, legal_document_catalog_link_label(document)))
        return matches

    def _document_matches_citation(self, document, citation: ParsedLegalCitation) -> bool:
        number, year = _document_number_year(document)
        if number is None or year is None:
            return False
        if number != citation.number or year != citation.year:
            return False

        document_type = (getattr(document, "document_type", "") or "").strip()
        if (
            citation.regulation_type is not None
            and document_type
            and citation.regulation_type != document_type
        ):
            return False
        return True

    @staticmethod
    def _candidate_fields(document) -> tuple[str, ...]:
        return (
            legal_document_catalog_link_label(document),
            legal_document_regulation_number(document),
            getattr(document, "title", "") or "",
            getattr(document, "short_title", "") or "",
            getattr(document, "number", "") or "",
        )

    @staticmethod
    def _result_from_matches(
        matches: list[tuple[int, str]],
    ) -> LegalDocumentMatchResult:
        unique: dict[int, str] = {}
        for document_id, label in matches:
            unique.setdefault(document_id, label)
        items = list(unique.items())
        if len(items) == 1:
            document_id, label = items[0]
            return LegalDocumentMatchResult(
                kind=LegalDocumentMatchKind.EXACT,
                document_id=document_id,
                candidates=((document_id, label),),
            )
        if len(items) > 1:
            return LegalDocumentMatchResult(
                kind=LegalDocumentMatchKind.AMBIGUOUS,
                candidates=tuple(items),
            )
        return LegalDocumentMatchResult(kind=LegalDocumentMatchKind.NONE)


# Zpětná kompatibilita názvů.
HazardCatalogLegalRequirementResolver = HazardCatalogLegalDocumentResolver
hazard_catalog_legal_document_resolver = HazardCatalogLegalDocumentResolver()
hazard_catalog_legal_requirement_resolver = hazard_catalog_legal_document_resolver
