"""Vyhledání právního požadavku pro AI návrh právní vazby (R19, R20b.1)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from moduly.pravni_pozadavky.constants import legal_requirement_merged_target_label
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
    is_similar_text_match,
    normalize_match_text,
)

REGULATION_TYPE_GOVERNMENT = "narizeni_vlady"
REGULATION_TYPE_DECREE = "vyhlaska"
REGULATION_TYPE_ACT = "zakon"

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


class LegalRequirementMatchKind(str, Enum):
    EXACT = "exact"
    AMBIGUOUS = "ambiguous"
    NONE = "none"


@dataclass(frozen=True)
class LegalRequirementMatchResult:
    kind: LegalRequirementMatchKind
    requirement_id: int | None = None
    candidates: tuple[tuple[int, str], ...] = ()


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


class HazardCatalogLegalRequirementResolver:
    def resolve(self, query: str) -> LegalRequirementMatchResult:
        raw_query = (query or "").strip()
        if not raw_query:
            return LegalRequirementMatchResult(kind=LegalRequirementMatchKind.NONE)

        by_code = legal_requirement_service.get_by_process_code(raw_query, active_only=True)
        if by_code is not None:
            return LegalRequirementMatchResult(
                kind=LegalRequirementMatchKind.EXACT,
                requirement_id=by_code.id,
                candidates=((by_code.id, legal_requirement_merged_target_label(by_code)),),
            )

        processes = legal_requirement_service.list_active_processes()
        citation = parse_legal_citation(raw_query)
        if citation is not None:
            citation_matches = self._match_by_citation(processes, citation)
            result = self._result_from_matches(citation_matches)
            if result.kind != LegalRequirementMatchKind.NONE:
                return result

        normalized_query = normalize_legal_citation_text(raw_query)
        if not normalized_query:
            return LegalRequirementMatchResult(kind=LegalRequirementMatchKind.NONE)

        exact_matches: list[tuple[int, str]] = []
        similar_matches: list[tuple[int, str]] = []
        for process in processes:
            label = legal_requirement_merged_target_label(process)
            fields = self._candidate_fields(process)
            if any(
                normalize_legal_citation_text(field) == normalized_query
                for field in fields
                if field
            ):
                exact_matches.append((process.id, label))
                continue
            if any(
                is_similar_text_match(
                    expand_legal_abbreviations(raw_query),
                    field,
                )
                for field in fields
                if field
            ):
                similar_matches.append((process.id, label))

        exact_result = self._result_from_matches(exact_matches)
        if exact_result.kind != LegalRequirementMatchKind.NONE:
            return exact_result
        return self._result_from_matches(similar_matches)

    def _match_by_citation(
        self,
        processes,
        citation: ParsedLegalCitation,
    ) -> list[tuple[int, str]]:
        matches: list[tuple[int, str]] = []
        for process in processes:
            if not self._process_matches_citation(process, citation):
                continue
            matches.append((process.id, legal_requirement_merged_target_label(process)))
        return matches

    def _process_matches_citation(self, process, citation: ParsedLegalCitation) -> bool:
        fields = self._candidate_fields(process)
        if not self._fields_contain_number_year(fields, citation):
            return False

        process_type = _infer_regulation_type(" ".join(field for field in fields if field))
        if (
            citation.regulation_type is not None
            and process_type is not None
            and citation.regulation_type != process_type
        ):
            return False
        return True

    @staticmethod
    def _fields_contain_number_year(
        fields: tuple[str, ...],
        citation: ParsedLegalCitation,
    ) -> bool:
        for field in fields:
            if not field:
                continue
            for match in _NUMBER_YEAR_RE.finditer(field):
                key = f"{int(match.group(1))}/{match.group(2)}"
                if key == citation.number_year_key:
                    return True
        return False

    @staticmethod
    def _candidate_fields(process) -> tuple[str, ...]:
        return (
            legal_requirement_merged_target_label(process),
            process.title or "",
            process.regulation_name or "",
            process.regulation_number or "",
            process.provision or "",
        )

    @staticmethod
    def _result_from_matches(
        matches: list[tuple[int, str]],
    ) -> LegalRequirementMatchResult:
        unique: dict[int, str] = {}
        for requirement_id, label in matches:
            unique.setdefault(requirement_id, label)
        items = list(unique.items())
        if len(items) == 1:
            requirement_id, label = items[0]
            return LegalRequirementMatchResult(
                kind=LegalRequirementMatchKind.EXACT,
                requirement_id=requirement_id,
                candidates=((requirement_id, label),),
            )
        if len(items) > 1:
            return LegalRequirementMatchResult(
                kind=LegalRequirementMatchKind.AMBIGUOUS,
                candidates=tuple(items),
            )
        return LegalRequirementMatchResult(kind=LegalRequirementMatchKind.NONE)


hazard_catalog_legal_requirement_resolver = HazardCatalogLegalRequirementResolver()
