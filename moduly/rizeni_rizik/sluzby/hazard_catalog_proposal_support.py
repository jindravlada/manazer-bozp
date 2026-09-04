"""Pomocné funkce pro klasifikaci a parsování návrhů AI v katalogu (R18g)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal

CATALOG_PROPOSAL_KIND_EVENT = "event"
CATALOG_PROPOSAL_KIND_ASSESSMENT = "assessment"
CATALOG_PROPOSAL_KIND_EXISTING_MEASURE = "existing_measure"
CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE = "required_measure"
CATALOG_PROPOSAL_KIND_EXPOSED_GROUP = "exposed_group"
CATALOG_PROPOSAL_KIND_LEGAL = "legal"
CATALOG_PROPOSAL_KIND_UNKNOWN = "unknown"

CATALOG_DUPLICATE_ACTION_SKIP = "skip"
CATALOG_DUPLICATE_ACTION_MERGE = "merge"
CATALOG_DUPLICATE_ACTION_EDIT = "edit"
CATALOG_DUPLICATE_ACTION_CANCEL = "cancel"
CATALOG_DUPLICATE_ACTION_CREATE = "create"

CATALOG_DUPLICATE_MATCH_EXACT = "exact"
CATALOG_DUPLICATE_MATCH_SIMILAR = "similar"

CATALOG_CONFLICT_TYPE_DUPLICATE = "duplicate"
CATALOG_CONFLICT_TYPE_REQUIREMENT_CHOICE = "requirement_choice"
CATALOG_CONFLICT_TYPE_ASSESSMENT_CHOICE = "assessment_choice"
CATALOG_CONFLICT_TYPE_ASSESSMENT_CREATE = "assessment_create"


@dataclass(frozen=True)
class CatalogProposalPayload:
    description: str = ""
    note: str = ""
    conclusion: str = ""
    severity: str = ""
    exposed_group_ids: tuple[int, ...] = ()
    legal_document_id: int | None = None
    legal_requirement_id: int | None = None


@dataclass(frozen=True)
class CatalogAssessmentCandidate:
    export_id: str
    event_name: str
    group_name: str
    assessment_id: int
    template_event_id: int


@dataclass(frozen=True)
class CatalogProposalDuplicate:
    kind: str
    match_type: str
    existing_label: str
    existing_id: int | None = None
    proposal_label: str = ""


@dataclass(frozen=True)
class CatalogProposalConflict:
    proposal_id: int
    proposal_label: str
    conflict_type: str = CATALOG_CONFLICT_TYPE_DUPLICATE
    duplicate: CatalogProposalDuplicate | None = None
    requirement_candidates: tuple[tuple[int, str], ...] = ()
    assessment_candidates: tuple[CatalogAssessmentCandidate, ...] = ()
    template_event_choices: tuple[tuple[int, str], ...] = ()


@dataclass
class CatalogIncorporatePlan:
    resolutions: dict[int, str]
    conflicts: list[CatalogProposalConflict]
    pending_proposal_ids: list[int]


def normalize_match_text(text: str) -> str:
    return " ".join((text or "").strip().split()).casefold()


def is_exact_text_match(left: str, right: str) -> bool:
    return normalize_match_text(left) == normalize_match_text(right)


def is_similar_text_match(left: str, right: str) -> bool:
    left_normalized = normalize_match_text(left)
    right_normalized = normalize_match_text(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return False
    if left_normalized in right_normalized or right_normalized in left_normalized:
        return True
    from difflib import SequenceMatcher

    return SequenceMatcher(None, left_normalized, right_normalized).ratio() >= 0.72


def is_codebook_proposal_kind(kind: str) -> bool:
    return kind in {
        CATALOG_PROPOSAL_KIND_EXPOSED_GROUP,
    }


def requires_dialog_for_duplicate(duplicate: CatalogProposalDuplicate) -> bool:
    return duplicate.match_type == CATALOG_DUPLICATE_MATCH_SIMILAR


def format_incorporate_summary(
    *,
    newly_incorporated: int,
    used_existing: int,
    requires_manual_decision: int,
    skipped: int,
    rejected: int,
    revision: int | None,
) -> str:
    from moduly.rizeni_rizik.constants_library import CATALOG_AI_PROPOSAL_INCORPORATE_SUMMARY

    return CATALOG_AI_PROPOSAL_INCORPORATE_SUMMARY.format(
        newly_incorporated=newly_incorporated,
        used_existing=used_existing,
        requires_manual_decision=requires_manual_decision,
        skipped=skipped,
        rejected=rejected,
        revision=revision if revision is not None else "—",
    )


def area_matches(area: str, needles: tuple[str, ...]) -> bool:
    normalized = (area or "").casefold()
    return any(needle in normalized for needle in needles)


def classify_catalog_proposal(proposal: AiUnassignedProposal) -> str:
    area = (proposal.area or "").casefold()
    if area_matches(area, ("právn", "pravni", "předpis", "predpis", "vazb", "legal")):
        return CATALOG_PROPOSAL_KIND_LEGAL
    if area_matches(area, ("událost", "udalost", "nežádouc", "nezadouc")):
        return CATALOG_PROPOSAL_KIND_EVENT
    if area_matches(area, ("ohrožen", "ohrozen", "skupin")) and not area_matches(
        area,
        ("posouzen", "posouzeni"),
    ):
        return CATALOG_PROPOSAL_KIND_EXPOSED_GROUP
    if area_matches(
        area,
        (
            "kontroln",
            "otázk",
            "otazk",
            "navazuj",
            "potřeb",
            "potreb",
            "dalš",
            "dals",
        ),
    ):
        return CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE
    if area_matches(area, ("posouzen", "rizik", "násled", "nasled", "ohrožen", "ohrozen")):
        return CATALOG_PROPOSAL_KIND_ASSESSMENT
    if area_matches(area, ("potřeb", "potreb", "dalš", "dals")):
        return CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE
    if area_matches(
        area,
        (
            "existujíc",
            "existujic",
            "zásad",
            "zasad",
            "ochrann",
            "organizač",
            "organizac",
            "oopp",
            "bariér",
            "barier",
            "technick",
            "opatřen",
            "opatren",
        ),
    ):
        return CATALOG_PROPOSAL_KIND_EXISTING_MEASURE
    return CATALOG_PROPOSAL_KIND_UNKNOWN


def parse_proposal_payload(proposal: AiUnassignedProposal) -> CatalogProposalPayload:
    raw = proposal.payload_json or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    group_ids: list[int] = []
    seen: set[int] = set()
    for raw in data.get("exposed_group_ids") or []:
        parsed = _parse_optional_int(raw)
        if parsed is None or parsed in seen:
            continue
        seen.add(parsed)
        group_ids.append(parsed)
    return CatalogProposalPayload(
        description=str(data.get("description") or "").strip(),
        note=str(data.get("note") or "").strip(),
        conclusion=str(data.get("conclusion") or "").strip(),
        severity=str(data.get("severity") or "").strip(),
        exposed_group_ids=tuple(group_ids),
        legal_document_id=_parse_optional_int(data.get("legal_document_id")),
        legal_requirement_id=_parse_optional_int(data.get("legal_requirement_id")),
    )


def _parse_optional_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def proposal_payload_to_json(payload: CatalogProposalPayload) -> str:
    return json.dumps(
        {
            "description": payload.description,
            "note": payload.note,
            "conclusion": payload.conclusion,
            "severity": payload.severity,
            "exposed_group_ids": list(payload.exposed_group_ids),
            "legal_document_id": payload.legal_document_id,
            "legal_requirement_id": payload.legal_requirement_id,
        },
        ensure_ascii=False,
    )


def merge_payload(existing: CatalogProposalPayload, updates: dict[str, Any]) -> CatalogProposalPayload:
    data = {
        "description": existing.description,
        "note": existing.note,
        "conclusion": existing.conclusion,
        "severity": existing.severity,
        "exposed_group_ids": existing.exposed_group_ids,
        "legal_document_id": existing.legal_document_id,
        "legal_requirement_id": existing.legal_requirement_id,
    }
    for key, value in updates.items():
        if key not in data or value is None:
            continue
        if key in {"legal_document_id", "legal_requirement_id"}:
            data[key] = _parse_optional_int(value)
        elif key == "exposed_group_ids":
            ids: list[int] = []
            seen: set[int] = set()
            for raw in value if isinstance(value, (list, tuple)) else ():
                parsed = _parse_optional_int(raw)
                if parsed is None or parsed in seen:
                    continue
                seen.add(parsed)
                ids.append(parsed)
            data[key] = tuple(ids)
        else:
            data[key] = str(value).strip()
    return CatalogProposalPayload(**data)
