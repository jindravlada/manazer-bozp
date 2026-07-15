"""Parsování odpovědi AI – JSON 1.1 s fallbackem na textový formát."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_FORMAT_JSON_1_1,
    AI_PEER_REVIEW_FORMAT_JSON_2_0,
    AI_PEER_REVIEW_FORMAT_TEXT,
    AI_PEER_REVIEW_FORMAT_TEXT_2_0,
    AI_PEER_REVIEW_SCHEMA_VERSION,
    AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
)
from core.ai_oponentni.proposal_package_types import AiProposalPackage
from core.ai_oponentni.sluzby.proposal_package_parser import (
    parse_ai_proposal_packages_response,
)
from core.ai_oponentni.types import AiPeerReviewParseResult, AiProposal


from core.ai_oponentni.sluzby.parse_errors import AiPeerReviewParseError

_AREA_RE = re.compile(r"^oblast\s*:\s*(.+)$", re.IGNORECASE)
_NAME_RE = re.compile(r"^návrh\s*:\s*(.+)$", re.IGNORECASE)
_PARENT_RE = re.compile(r"^rodič\s*:\s*(.+)$", re.IGNORECASE)
_REASON_RE = re.compile(r"^zdůvodnění\s*:\s*(.*)$", re.IGNORECASE)

_NULLISH_PARENT = {"", "—", "-", "–", "null", "none", "nil"}


@dataclass
class _JsonProposalParseOutcome:
    proposals: list[AiProposal]
    skip_reasons: list[str]


def parse_ai_peer_review_response(
    text: str,
    *,
    expected_source_identification_number: str | None = None,
    require_proposal_packages: bool = False,
) -> AiPeerReviewParseResult:
    """
    Pořadí:
    1. pokus o JSON,
    2. pokud jde o schema 2.0 → parser balíků,
    3. pokud jde o schema 1.1 → JSON parser atomických návrhů,
    4. jinak textový parser (1.1 nebo 2.0 podle režimu).
    """
    raw = text if text is not None else ""
    if not raw.strip():
        return AiPeerReviewParseResult(
            format_label=(
                AI_PEER_REVIEW_FORMAT_TEXT_2_0
                if require_proposal_packages
                else AI_PEER_REVIEW_FORMAT_TEXT
            ),
        )

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        loaded = None

    if isinstance(loaded, dict) and _looks_like_schema_response(loaded):
        schema_version = str(loaded.get("schema_version") or "")
        if schema_version == AI_PEER_REVIEW_SCHEMA_VERSION_2_0 or (
            require_proposal_packages and "proposal_packages" in loaded
        ):
            package_result = parse_ai_proposal_packages_response(
                raw,
                expected_source_reference=expected_source_identification_number,
            )
            return AiPeerReviewParseResult(
                packages=package_result.packages,
                format_label=package_result.format_label,
                schema_version=package_result.schema_version,
                source_reference=package_result.source_reference,
                skipped_count=len(package_result.skip_reasons),
                skip_reasons=package_result.skip_reasons,
            )
        if require_proposal_packages:
            raise AiPeerReviewParseError(
                "Katalog zdrojů rizik vyžaduje odpověď ve formátu schema 2.0."
            )
        proposals, skip_reasons = _parse_json_schema_response(
            loaded,
            expected_source_identification_number=expected_source_identification_number,
        )
        return AiPeerReviewParseResult(
            proposals=proposals,
            format_label=AI_PEER_REVIEW_FORMAT_JSON_1_1,
            schema_version=AI_PEER_REVIEW_SCHEMA_VERSION,
            skipped_count=len(skip_reasons),
            skip_reasons=skip_reasons,
        )

    if require_proposal_packages:
        package_result = parse_ai_proposal_packages_response(
            raw,
            expected_source_reference=expected_source_identification_number,
        )
        return AiPeerReviewParseResult(
            packages=package_result.packages,
            format_label=package_result.format_label,
            schema_version=package_result.schema_version or AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
            skipped_count=len(package_result.skip_reasons),
            skip_reasons=package_result.skip_reasons,
        )

    text_proposals = parse_ai_peer_review_text_response(raw)
    return AiPeerReviewParseResult(
        proposals=text_proposals,
        format_label=AI_PEER_REVIEW_FORMAT_TEXT,
    )


def parse_ai_peer_review_text_response(text: str) -> list[AiProposal]:
    """
    Očekávaný formát bloku:

    Oblast: ...
    Návrh: ...
    Rodič: ITEM-001   (volitelné; — = null)
    Zdůvodnění: ...
    """
    if not (text or "").strip():
        return []

    proposals: list[AiProposal] = []
    current: dict[str, str | None] = {}
    collecting_reason = False

    def flush() -> None:
        nonlocal current, collecting_reason
        area = (current.get("area") or "").strip()
        name = (current.get("name") or "").strip()
        reasoning = (current.get("reasoning") or "").strip()
        parent_raw = (current.get("parent_export_id") or "").strip()
        parent_export_id = None
        if parent_raw and parent_raw.casefold() not in _NULLISH_PARENT:
            parent_export_id = parent_raw
        if area and name:
            proposals.append(
                AiProposal(
                    area=area,
                    name=name,
                    reasoning=reasoning,
                    parent_export_id=parent_export_id,
                )
            )
        current = {}
        collecting_reason = False

    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            if current.get("area") and current.get("name"):
                flush()
            continue

        area_match = _AREA_RE.match(line)
        if area_match:
            if current.get("area") and current.get("name"):
                flush()
            current = {"area": area_match.group(1).strip()}
            collecting_reason = False
            continue

        name_match = _NAME_RE.match(line)
        if name_match:
            current["name"] = name_match.group(1).strip()
            collecting_reason = False
            continue

        parent_match = _PARENT_RE.match(line)
        if parent_match:
            current["parent_export_id"] = parent_match.group(1).strip()
            collecting_reason = False
            continue

        reason_match = _REASON_RE.match(line)
        if reason_match:
            current["reasoning"] = reason_match.group(1).strip()
            collecting_reason = True
            continue

        if collecting_reason:
            existing = current.get("reasoning") or ""
            current["reasoning"] = f"{existing} {line}".strip() if existing else line

    if current.get("area") and current.get("name"):
        flush()

    return proposals


def _looks_like_schema_response(payload: dict) -> bool:
    return "schema_version" in payload or "proposals" in payload


def _parse_json_schema_response(
    payload: dict,
    *,
    expected_source_identification_number: str | None,
) -> tuple[list[AiProposal], list[str]]:
    if not isinstance(payload, dict):
        raise AiPeerReviewParseError("Kořen JSON odpovědi musí být objekt.")

    schema_version = payload.get("schema_version")
    if schema_version is None:
        raise AiPeerReviewParseError("V JSON odpovědi chybí pole schema_version.")
    if str(schema_version) != AI_PEER_REVIEW_SCHEMA_VERSION:
        raise AiPeerReviewParseError(
            f"Nepodporovaná verze schématu „{schema_version}“. "
            f"Podporována je {AI_PEER_REVIEW_SCHEMA_VERSION}."
        )

    source_number = payload.get("source_identification_number")
    if source_number is None or not str(source_number).strip():
        raise AiPeerReviewParseError(
            "V JSON odpovědi chybí pole source_identification_number."
        )
    if expected_source_identification_number:
        actual = str(source_number).strip()
        expected = expected_source_identification_number.strip()
        if actual != expected:
            raise AiPeerReviewParseError(
                f"Číslo identifikace v odpovědi ({actual}) neodpovídá "
                f"otevřené identifikaci ({expected})."
            )

    if "proposals" not in payload:
        raise AiPeerReviewParseError("V JSON odpovědi chybí pole proposals.")
    proposals_raw = payload.get("proposals")
    if not isinstance(proposals_raw, list):
        raise AiPeerReviewParseError("Pole proposals musí být pole (array).")

    outcome = _JsonProposalParseOutcome(proposals=[], skip_reasons=[])
    for index, item in enumerate(proposals_raw, start=1):
        proposal, reason = _parse_one_json_proposal(item, index=index)
        if proposal is None:
            outcome.skip_reasons.append(reason or f"Návrh #{index}: neplatný.")
            continue
        outcome.proposals.append(proposal)
    return outcome.proposals, outcome.skip_reasons


def _parse_one_json_proposal(
    item: object,
    *,
    index: int,
) -> tuple[AiProposal | None, str | None]:
    label = f"Návrh #{index}"
    if not isinstance(item, dict):
        return None, f"{label}: není objekt."

    missing = [
        field
        for field in ("proposal_id", "area", "name", "parent_export_id", "reasoning")
        if field not in item
    ]
    if missing:
        return None, f"{label}: chybí povinná pole ({', '.join(missing)})."

    proposal_id = item.get("proposal_id")
    area = item.get("area")
    name = item.get("name")
    parent_export_id = item.get("parent_export_id")
    reasoning = item.get("reasoning")

    if not isinstance(proposal_id, str) or not proposal_id.strip():
        return None, f"{label}: proposal_id musí být neprázdný řetězec."
    if not isinstance(area, str) or not area.strip():
        return None, f"{label}: area musí být neprázdný řetězec."
    if not isinstance(name, str) or not name.strip():
        return None, f"{label}: name musí být neprázdný řetězec."
    if not isinstance(reasoning, str):
        return None, f"{label}: reasoning musí být řetězec."
    if parent_export_id is not None and not isinstance(parent_export_id, str):
        return None, f"{label}: parent_export_id musí být string nebo null."

    normalized_parent: str | None
    if parent_export_id is None:
        normalized_parent = None
    else:
        stripped = parent_export_id.strip()
        if not stripped or stripped.casefold() in _NULLISH_PARENT:
            normalized_parent = None
        else:
            normalized_parent = stripped

    return (
        AiProposal(
            proposal_id=proposal_id.strip(),
            area=area.strip(),
            name=name.strip(),
            reasoning=reasoning.strip(),
            parent_export_id=normalized_parent,
        ),
        None,
    )
