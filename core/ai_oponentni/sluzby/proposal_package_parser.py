"""Parsování a validace návrhových balíků AI oponentury (schema 2.0)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from core.ai_oponentni.constants import (
    AI_MEASURE_REC_EDIT_EXISTING,
    AI_MEASURE_REC_EDIT_REQUIRED,
    AI_MEASURE_REC_NEW_REQUIRED,
    AI_MEASURE_REC_NO_CHANGE,
    AI_MEASURE_RECOMMENDATION_TYPES,
    AI_PEER_REVIEW_FORMAT_JSON_2_0,
    AI_PEER_REVIEW_FORMAT_TEXT_2_0,
    AI_PEER_REVIEW_NOT_AI_RESPONSE,
    AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
    AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
    AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
)
from core.ai_oponentni.proposal_package_types import (
    AiProposalPackage,
    AiProposalPackageAssessment,
    AiProposalPackageEvent,
    AiProposalPackageLegalLink,
    AiProposalPackageMeasure,
    AiProposalPackageParseResult,
)
from core.ai_oponentni.sluzby.parse_errors import AiPeerReviewParseError
from moduly.rizeni_rizik.constants import RISK_SEVERITIES

_PACKAGE_HEADER_RE = re.compile(r"^balík\s*:\s*(.+)$", re.IGNORECASE)
_PACKAGE_TYPE_RE = re.compile(r"^typ\s*:\s*(.+)$", re.IGNORECASE)
_TARGET_EVENT_RE = re.compile(r"^cílová\s+událost\s*:\s*(.+)$", re.IGNORECASE)
_EVENT_SECTION_RE = re.compile(r"^událost\s*:\s*$", re.IGNORECASE)
_ASSESSMENT_SECTION_RE = re.compile(r"^posouzení\s*:\s*$", re.IGNORECASE)
_EXISTING_MEASURES_RE = re.compile(
    r"^(existující\s+opatření|zásady\s+bezpečné\s+práce)\s*:\s*$",
    re.IGNORECASE,
)
_REQUIRED_MEASURES_RE = re.compile(
    r"^(potřebná\s+opatření|navazující\s+opatření|"
    r"kontrolní\s+otázky(?:\s+pro\s+revizi(?:\s+posouzení)?\s+rizik)?)\s*:\s*$",
    re.IGNORECASE,
)
_LEGAL_LINKS_RE = re.compile(r"^právní\s+vazby\s*:\s*$", re.IGNORECASE)
_REASONING_SECTION_RE = re.compile(r"^zdůvodnění\s*:\s*(.*)$", re.IGNORECASE)
_EXPOSED_GROUP_RE = re.compile(r"^ohrožená\s+skupina\s*:\s*(.+)$", re.IGNORECASE)
_EXPOSED_GROUPS_RE = re.compile(r"^ohrožené\s+skupiny\s*:\s*(.+)$", re.IGNORECASE)
_SEVERITY_RE = re.compile(r"^závažnost\s*:\s*(.+)$", re.IGNORECASE)
_CONCLUSION_RE = re.compile(r"^závěr\s*:\s*(.+)$", re.IGNORECASE)
_MEASURE_ITEM_RE = re.compile(r"^-\s*(.+)$")

_TEXT_PACKAGE_TYPE_LABELS = {
    "nová událost": AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
    "doplnění existující události": AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
    "doplnění události": AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
    "extend_event": AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
    "new_event": AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
}


@dataclass
class _PackageParseOutcome:
    packages: list[AiProposalPackage] = field(default_factory=list)
    skip_reasons: list[str] = field(default_factory=list)


def parse_ai_proposal_packages_response(
    text: str,
    *,
    expected_source_reference: str | None = None,
) -> AiProposalPackageParseResult:
    raw = text if text is not None else ""
    if not raw.strip():
        return AiProposalPackageParseResult(
            format_label=AI_PEER_REVIEW_FORMAT_TEXT_2_0,
        )

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        loaded = None

    if isinstance(loaded, dict) and _looks_like_package_schema_response(loaded):
        outcome = _parse_json_package_response(
            loaded,
            expected_source_reference=expected_source_reference,
        )
        return AiProposalPackageParseResult(
            packages=outcome.packages,
            format_label=AI_PEER_REVIEW_FORMAT_JSON_2_0,
            schema_version=AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
            source_reference=str(loaded.get("source_reference") or "").strip(),
            skip_reasons=outcome.skip_reasons,
        )

    if isinstance(loaded, dict) and _looks_like_export_or_response_schema(loaded):
        raise AiPeerReviewParseError(AI_PEER_REVIEW_NOT_AI_RESPONSE)

    text_packages, skip_reasons = _parse_text_package_response(raw)
    return AiProposalPackageParseResult(
        packages=text_packages,
        format_label=AI_PEER_REVIEW_FORMAT_TEXT_2_0,
        schema_version=AI_PEER_REVIEW_SCHEMA_VERSION_2_0 if text_packages else "",
        skip_reasons=skip_reasons,
    )


def _looks_like_package_schema_response(payload: dict) -> bool:
    """True jen pro instanci odpovědi AI (ne JSON Schema ani zadání)."""
    source_reference = payload.get("source_reference")
    if source_reference is None or not str(source_reference).strip():
        return False
    return "proposal_packages" in payload or "measure_recommendations" in payload


def _looks_like_export_or_response_schema(payload: dict) -> bool:
    """Exportní ZIP (zadani/schema) nebo JSON Schema – není odpověď AI."""
    if "ai_instruction" in payload or "source_data" in payload:
        return True
    if payload.get("user_instruction"):
        return True
    if "$defs" in payload:
        return True
    if payload.get("type") == "object" and isinstance(payload.get("properties"), dict):
        return True
    if "export_type" in payload:
        return True
    if "catalog_source" in payload and "source_reference" not in payload:
        return True
    if str(payload.get("schema_version") or "") == AI_PEER_REVIEW_SCHEMA_VERSION_2_0:
        if "proposal_packages" not in payload and "measure_recommendations" not in payload:
            return True
    return False


def _parse_json_package_response(
    payload: dict,
    *,
    expected_source_reference: str | None,
) -> _PackageParseOutcome:
    schema_version = payload.get("schema_version")
    if schema_version is None:
        raise AiPeerReviewParseError("V JSON odpovědi chybí pole schema_version.")
    if str(schema_version) != AI_PEER_REVIEW_SCHEMA_VERSION_2_0:
        raise AiPeerReviewParseError(
            f"Nepodporovaná verze schématu „{schema_version}“. "
            f"Podporována je {AI_PEER_REVIEW_SCHEMA_VERSION_2_0}."
        )

    source_reference = payload.get("source_reference")
    if source_reference is None or not str(source_reference).strip():
        raise AiPeerReviewParseError("V JSON odpovědi chybí pole source_reference.")
    if expected_source_reference:
        actual = str(source_reference).strip()
        expected = expected_source_reference.strip()
        if actual != expected:
            raise AiPeerReviewParseError(
                f"Reference zdroje v odpovědi ({actual}) neodpovídá "
                f"otevřenému zdroji ({expected})."
            )

    packages_raw = payload.get("proposal_packages")
    recommendations_raw = payload.get("measure_recommendations")
    if packages_raw is None and recommendations_raw is None:
        raise AiPeerReviewParseError(
            "V JSON odpovědi chybí pole proposal_packages "
            "nebo measure_recommendations."
        )
    if packages_raw is not None and not isinstance(packages_raw, list):
        raise AiPeerReviewParseError("Pole proposal_packages musí být pole (array).")
    if recommendations_raw is not None and not isinstance(recommendations_raw, list):
        raise AiPeerReviewParseError(
            "Pole measure_recommendations musí být pole (array)."
        )

    outcome = _PackageParseOutcome()
    for index, item in enumerate(packages_raw or [], start=1):
        package, reason = _parse_one_json_package(item, index=index)
        if package is None:
            outcome.skip_reasons.append(reason or f"Balík #{index}: neplatný.")
            continue
        outcome.packages.append(package)

    for index, item in enumerate(recommendations_raw or [], start=1):
        package, reason = _parse_one_measure_recommendation(item, index=index)
        if package is None:
            outcome.skip_reasons.append(
                reason or f"Doporučení k opatření #{index}: neplatné."
            )
            continue
        outcome.packages.append(package)
    return outcome


def _parse_one_measure_recommendation(
    item: object,
    *,
    index: int,
) -> tuple[AiProposalPackage | None, str | None]:
    label = f"Doporučení k opatření #{index}"
    if not isinstance(item, dict):
        return None, f"{label}: není objekt."

    recommendation_id = str(
        item.get("recommendation_id") or item.get("package_id") or ""
    ).strip()
    if not recommendation_id:
        return None, f"{label}: chybí recommendation_id."

    rec_type = _normalize_measure_recommendation_type(item.get("typ") or item.get("type"))
    if rec_type is None:
        raw_type = item.get("typ") if "typ" in item else item.get("type")
        return None, f"{label}: neznámý typ doporučení „{raw_type}“."

    reasoning = str(item.get("reasoning") or "").strip()
    if not reasoning:
        return None, f"{label}: chybí reasoning."

    proposed_text = str(
        item.get("proposed_text")
        or item.get("proposed_wording")
        or item.get("description")
        or ""
    ).strip()
    target_export_id = _normalize_target_event(
        item.get("target_export_id") or item.get("parent_export_id")
    )

    if rec_type in {
        AI_MEASURE_REC_EDIT_REQUIRED,
        AI_MEASURE_REC_EDIT_EXISTING,
    }:
        if not target_export_id:
            return None, f"{label}: úprava vyžaduje target_export_id."
        if not proposed_text:
            return None, f"{label}: úprava vyžaduje proposed_text."
    elif rec_type == AI_MEASURE_REC_NEW_REQUIRED:
        if not target_export_id:
            return None, f"{label}: nové opatření vyžaduje target_export_id (ASSESSMENT-…)."
        if not proposed_text:
            return None, f"{label}: nové opatření vyžaduje proposed_text."

    return (
        AiProposalPackage(
            package_id=recommendation_id,
            package_type=rec_type,
            target_event_export_id=None,
            event=None,
            assessments=(),
            legal_links=(),
            reasoning=reasoning,
            target_export_id=target_export_id,
            proposed_text=proposed_text,
        ),
        None,
    )


def _normalize_measure_recommendation_type(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().casefold().replace(" ", "_").replace("-", "_")
    aliases = {
        "beze_zmen": AI_MEASURE_REC_NO_CHANGE,
        "bez_zmen": AI_MEASURE_REC_NO_CHANGE,
        "no_change": AI_MEASURE_REC_NO_CHANGE,
        "upravit_navazujici_opatreni": AI_MEASURE_REC_EDIT_REQUIRED,
        "upravit_navazujici": AI_MEASURE_REC_EDIT_REQUIRED,
        "edit_required_measure": AI_MEASURE_REC_EDIT_REQUIRED,
        "upravit_kontrolni_otazku": AI_MEASURE_REC_EDIT_REQUIRED,
        "upravit_kontrolni_otazky": AI_MEASURE_REC_EDIT_REQUIRED,
        "upravit_zasady_bezpecne_prace": AI_MEASURE_REC_EDIT_EXISTING,
        "upravit_zasady": AI_MEASURE_REC_EDIT_EXISTING,
        "edit_existing_measure": AI_MEASURE_REC_EDIT_EXISTING,
        "nove_navazujici_opatreni": AI_MEASURE_REC_NEW_REQUIRED,
        "nove_navazujici": AI_MEASURE_REC_NEW_REQUIRED,
        "new_required_measure": AI_MEASURE_REC_NEW_REQUIRED,
        "nova_kontrolni_otazka": AI_MEASURE_REC_NEW_REQUIRED,
        "nove_kontrolni_otazky": AI_MEASURE_REC_NEW_REQUIRED,
    }
    resolved = aliases.get(normalized)
    if resolved is not None:
        return resolved
    if normalized in AI_MEASURE_RECOMMENDATION_TYPES:
        return normalized
    return None


def _parse_one_json_package(
    item: object,
    *,
    index: int,
) -> tuple[AiProposalPackage | None, str | None]:
    label = f"Balík #{index}"
    if not isinstance(item, dict):
        return None, f"{label}: není objekt."

    package_id = str(item.get("package_id") or "").strip()
    if not package_id:
        return None, f"{label}: chybí package_id."

    package_type = _normalize_package_type(item.get("package_type"))
    if package_type is None:
        return None, f"{label}: neplatný package_type."

    target_event_export_id = _normalize_target_event(item.get("target_event_export_id"))
    event = _parse_event_payload(item.get("event"))
    assessments = _parse_assessments_payload(item.get("assessments"))
    legal_links = _parse_legal_links_payload(item.get("legal_links"))
    reasoning = str(item.get("reasoning") or "").strip()

    validation_error = _validate_package(
        package_type=package_type,
        target_event_export_id=target_event_export_id,
        event=event,
        assessments=assessments,
        label=label,
    )
    if validation_error:
        return None, validation_error

    return (
        AiProposalPackage(
            package_id=package_id,
            package_type=package_type,
            target_event_export_id=target_event_export_id,
            event=event,
            assessments=assessments,
            legal_links=legal_links,
            reasoning=reasoning,
        ),
        None,
    )


def _parse_event_payload(payload: object) -> AiProposalPackageEvent | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        return None
    return AiProposalPackageEvent(
        name=str(payload.get("name") or "").strip(),
        description=str(payload.get("description") or "").strip(),
        note=str(payload.get("note") or "").strip(),
    )


def _parse_assessments_payload(payload: object) -> tuple[AiProposalPackageAssessment, ...]:
    if not isinstance(payload, list):
        return ()
    assessments: list[AiProposalPackageAssessment] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        existing = tuple(
            AiProposalPackageMeasure(
                description=str(measure.get("description") or "").strip(),
                note=str(measure.get("note") or "").strip(),
            )
            for measure in (item.get("existing_measures") or [])
            if isinstance(measure, dict)
            and str(measure.get("description") or "").strip()
        )
        required = tuple(
            AiProposalPackageMeasure(
                description=str(measure.get("description") or "").strip(),
                note=str(measure.get("note") or "").strip(),
            )
            for measure in (item.get("required_measures") or [])
            if isinstance(measure, dict)
            and str(measure.get("description") or "").strip()
        )
        assessments.append(
            AiProposalPackageAssessment(
                exposed_group=str(item.get("exposed_group") or "").strip(),
                exposed_groups=tuple(
                    str(name or "").strip()
                    for name in (item.get("exposed_groups") or [])
                    if str(name or "").strip()
                ),
                severity=str(item.get("severity") or "").strip(),
                conclusion=str(item.get("conclusion") or "").strip(),
                existing_measures=existing,
                required_measures=required,
            ),
        )
    return tuple(assessments)


def _parse_legal_links_payload(payload: object) -> tuple[AiProposalPackageLegalLink, ...]:
    if not isinstance(payload, list):
        return ()
    links: list[AiProposalPackageLegalLink] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        reference = str(item.get("reference") or "").strip()
        if not reference:
            continue
        links.append(
            AiProposalPackageLegalLink(
                reference=reference,
                reasoning=str(item.get("reasoning") or "").strip(),
            ),
        )
    return tuple(links)


def _normalize_package_type(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().casefold()
    if normalized in {AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT, "new event"}:
        return AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT
    if normalized in {
        AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
        "extend event",
        "extend_existing_event",
    }:
        return AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT
    if normalized in _TEXT_PACKAGE_TYPE_LABELS:
        return _TEXT_PACKAGE_TYPE_LABELS[normalized]
    return None


def _normalize_target_event(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.casefold() in {"null", "none", "—", "-", "–"}:
        return None
    return stripped


def _validate_package(
    *,
    package_type: str,
    target_event_export_id: str | None,
    event: AiProposalPackageEvent | None,
    assessments: tuple[AiProposalPackageAssessment, ...],
    label: str,
) -> str | None:
    if package_type in AI_MEASURE_RECOMMENDATION_TYPES:
        return None

    if package_type == AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT:
        if event is None or not event.name.strip():
            return f"{label}: nová událost musí mít název."
    elif package_type == AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT:
        if not target_event_export_id:
            return f"{label}: doplnění události vyžaduje target_event_export_id."

    if not assessments:
        return f"{label}: balík musí obsahovat alespoň jedno posouzení."

    for assessment_index, assessment in enumerate(assessments, start=1):
        assessment_label = f"{label}, posouzení #{assessment_index}"
        if not (assessment.exposed_groups or assessment.exposed_group.strip()):
            return f"{assessment_label}: chybí ohrožená skupina."
        if assessment.severity.strip().casefold() not in RISK_SEVERITIES:
            return (
                f"{assessment_label}: neplatná závažnost "
                f"„{assessment.severity}“."
            )
    return None


def _parse_text_package_response(text: str) -> tuple[list[AiProposalPackage], list[str]]:
    blocks = _split_text_packages(text)
    packages: list[AiProposalPackage] = []
    skip_reasons: list[str] = []
    for index, block in enumerate(blocks, start=1):
        package, reason = _parse_one_text_package(block, index=index)
        if package is None:
            skip_reasons.append(reason or f"Balík #{index}: neplatný.")
            continue
        packages.append(package)
    return packages, skip_reasons


def _split_text_packages(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").split("\n")
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _PACKAGE_HEADER_RE.match(line.strip()) and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(block).strip() for block in blocks if any(line.strip() for line in block)]


def _parse_one_text_package(
    block: str,
    *,
    index: int,
) -> tuple[AiProposalPackage | None, str | None]:
    label = f"Balík #{index}"
    package_id = ""
    package_type: str | None = None
    target_event_export_id: str | None = None
    event_lines: list[str] = []
    reasoning_lines: list[str] = []
    legal_links: list[AiProposalPackageLegalLink] = []
    assessments: list[AiProposalPackageAssessment] = []

    section = "header"
    current_assessment: dict[str, object] | None = None
    measure_mode: str | None = None

    def flush_assessment() -> None:
        nonlocal current_assessment
        if current_assessment is None:
            return
        existing = tuple(current_assessment.get("existing_measures") or ())
        required = tuple(current_assessment.get("required_measures") or ())
        assessments.append(
            AiProposalPackageAssessment(
                exposed_group=str(current_assessment.get("exposed_group") or "").strip(),
                exposed_groups=tuple(
                    str(name or "").strip()
                    for name in (current_assessment.get("exposed_groups") or [])
                    if str(name or "").strip()
                ),
                severity=str(current_assessment.get("severity") or "").strip(),
                conclusion=str(current_assessment.get("conclusion") or "").strip(),
                existing_measures=existing,
                required_measures=required,
            ),
        )
        current_assessment = None

    for raw_line in block.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        header_match = _PACKAGE_HEADER_RE.match(line)
        if header_match:
            package_id = header_match.group(1).strip()
            continue

        type_match = _PACKAGE_TYPE_RE.match(line)
        if type_match:
            package_type = _normalize_package_type(type_match.group(1).strip())
            continue

        target_match = _TARGET_EVENT_RE.match(line)
        if target_match:
            target_event_export_id = _normalize_target_event(target_match.group(1).strip())
            continue

        if _EVENT_SECTION_RE.match(line):
            flush_assessment()
            section = "event"
            measure_mode = None
            continue

        if _ASSESSMENT_SECTION_RE.match(line):
            flush_assessment()
            section = "assessment"
            current_assessment = {
                "exposed_groups": [],
                "existing_measures": [],
                "required_measures": [],
            }
            measure_mode = None
            continue

        if _EXISTING_MEASURES_RE.match(line):
            measure_mode = "existing"
            continue

        if _REQUIRED_MEASURES_RE.match(line):
            measure_mode = "required"
            continue

        if _LEGAL_LINKS_RE.match(line):
            flush_assessment()
            section = "legal"
            measure_mode = None
            continue

        reason_match = _REASONING_SECTION_RE.match(line)
        if reason_match:
            flush_assessment()
            section = "reasoning"
            measure_mode = None
            reasoning_lines = [reason_match.group(1).strip()] if reason_match.group(1).strip() else []
            continue

        if section == "event":
            event_lines.append(line)
            continue

        if section == "assessment" and current_assessment is not None:
            exposed_match = _EXPOSED_GROUP_RE.match(line)
            if exposed_match:
                groups = list(current_assessment.get("exposed_groups") or [])
                name = exposed_match.group(1).strip()
                if name:
                    groups.append(name)
                    current_assessment["exposed_groups"] = groups
                    if not current_assessment.get("exposed_group"):
                        current_assessment["exposed_group"] = name
                continue
            groups_match = _EXPOSED_GROUPS_RE.match(line)
            if groups_match:
                groups = list(current_assessment.get("exposed_groups") or [])
                for part in re.split(r"[;|]", groups_match.group(1)):
                    name = part.strip()
                    if name:
                        groups.append(name)
                current_assessment["exposed_groups"] = groups
                if groups and not current_assessment.get("exposed_group"):
                    current_assessment["exposed_group"] = groups[0]
                continue
            severity_match = _SEVERITY_RE.match(line)
            if severity_match:
                current_assessment["severity"] = severity_match.group(1).strip()
                continue
            conclusion_match = _CONCLUSION_RE.match(line)
            if conclusion_match:
                current_assessment["conclusion"] = conclusion_match.group(1).strip()
                continue
            measure_match = _MEASURE_ITEM_RE.match(line)
            if measure_match and measure_mode in {"existing", "required"}:
                measure = AiProposalPackageMeasure(description=measure_match.group(1).strip())
                key = f"{measure_mode}_measures"
                current_assessment[key].append(measure)
                continue

        if section == "legal":
            measure_match = _MEASURE_ITEM_RE.match(line)
            if measure_match:
                legal_links.append(
                    AiProposalPackageLegalLink(reference=measure_match.group(1).strip()),
                )
            continue

        if section == "reasoning":
            reasoning_lines.append(line)

    flush_assessment()

    if not package_id:
        return None, f"{label}: chybí identifikátor balíku (BALÍK: …)."
    if package_type is None:
        return None, f"{label}: chybí nebo je neplatný typ balíku."

    event = None
    if event_lines:
        event = AiProposalPackageEvent(
            name=event_lines[0].strip(),
            description="\n".join(event_lines[1:]).strip(),
        )

    validation_error = _validate_package(
        package_type=package_type,
        target_event_export_id=target_event_export_id,
        event=event,
        assessments=tuple(assessments),
        label=label,
    )
    if validation_error:
        return None, validation_error

    return (
        AiProposalPackage(
            package_id=package_id,
            package_type=package_type,
            target_event_export_id=target_event_export_id,
            event=event,
            assessments=tuple(assessments),
            legal_links=tuple(legal_links),
            reasoning="\n".join(reasoning_lines).strip(),
        ),
        None,
    )
