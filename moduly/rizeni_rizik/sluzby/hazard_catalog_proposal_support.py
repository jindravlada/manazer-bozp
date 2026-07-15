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


@dataclass(frozen=True)
class CatalogProposalPayload:
    description: str = ""
    note: str = ""
    consequence: str = ""
    conclusion: str = ""
    severity: str = ""


@dataclass(frozen=True)
class CatalogProposalDuplicate:
    kind: str
    existing_label: str
    existing_id: int | None = None


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
    if area_matches(area, ("posouzen", "rizik", "násled", "nasled", "ohrožen", "ohrozen")):
        return CATALOG_PROPOSAL_KIND_ASSESSMENT
    if area_matches(area, ("potřeb", "potreb", "dalš", "dals")):
        return CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE
    if area_matches(
        area,
        (
            "existujíc",
            "existujic",
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
    return CatalogProposalPayload(
        description=str(data.get("description") or "").strip(),
        note=str(data.get("note") or "").strip(),
        consequence=str(data.get("consequence") or "").strip(),
        conclusion=str(data.get("conclusion") or "").strip(),
        severity=str(data.get("severity") or "").strip(),
    )


def proposal_payload_to_json(payload: CatalogProposalPayload) -> str:
    return json.dumps(
        {
            "description": payload.description,
            "note": payload.note,
            "consequence": payload.consequence,
            "conclusion": payload.conclusion,
            "severity": payload.severity,
        },
        ensure_ascii=False,
    )


def merge_payload(existing: CatalogProposalPayload, updates: dict[str, Any]) -> CatalogProposalPayload:
    data = {
        "description": existing.description,
        "note": existing.note,
        "consequence": existing.consequence,
        "conclusion": existing.conclusion,
        "severity": existing.severity,
    }
    for key, value in updates.items():
        if key in data and value is not None:
            data[key] = str(value).strip()
    return CatalogProposalPayload(**data)
