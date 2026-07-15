"""Vyhledání právního požadavku pro AI návrh právní vazby (R19)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from moduly.pravni_pozadavky.constants import legal_requirement_merged_target_label
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
    is_exact_text_match,
    is_similar_text_match,
    normalize_match_text,
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


class HazardCatalogLegalRequirementResolver:
    def resolve(self, query: str) -> LegalRequirementMatchResult:
        normalized_query = normalize_match_text(query)
        if not normalized_query:
            return LegalRequirementMatchResult(kind=LegalRequirementMatchKind.NONE)

        by_code = legal_requirement_service.get_by_process_code(query.strip(), active_only=True)
        if by_code is not None:
            return LegalRequirementMatchResult(
                kind=LegalRequirementMatchKind.EXACT,
                requirement_id=by_code.id,
                candidates=((by_code.id, legal_requirement_merged_target_label(by_code)),),
            )

        processes = legal_requirement_service.list_active_processes()
        exact_matches: list[tuple[int, str]] = []
        similar_matches: list[tuple[int, str]] = []

        for process in processes:
            label = legal_requirement_merged_target_label(process)
            title = process.title or process.regulation_name or ""
            regulation = process.regulation_name or ""
            provision = process.provision or ""

            if any(
                is_exact_text_match(query, candidate)
                for candidate in (label, title, regulation, provision)
                if candidate
            ):
                exact_matches.append((process.id, label))
                continue

            if any(
                is_similar_text_match(query, candidate)
                for candidate in (label, title, regulation)
                if candidate
            ):
                similar_matches.append((process.id, label))

        if len(exact_matches) == 1:
            requirement_id, _ = exact_matches[0]
            return LegalRequirementMatchResult(
                kind=LegalRequirementMatchKind.EXACT,
                requirement_id=requirement_id,
                candidates=exact_matches,
            )
        if len(exact_matches) > 1:
            return LegalRequirementMatchResult(
                kind=LegalRequirementMatchKind.AMBIGUOUS,
                candidates=tuple(exact_matches),
            )
        if len(similar_matches) == 1:
            requirement_id, _ = similar_matches[0]
            return LegalRequirementMatchResult(
                kind=LegalRequirementMatchKind.EXACT,
                requirement_id=requirement_id,
                candidates=similar_matches,
            )
        if similar_matches:
            return LegalRequirementMatchResult(
                kind=LegalRequirementMatchKind.AMBIGUOUS,
                candidates=tuple(similar_matches),
            )
        return LegalRequirementMatchResult(kind=LegalRequirementMatchKind.NONE)


hazard_catalog_legal_requirement_resolver = HazardCatalogLegalRequirementResolver()
