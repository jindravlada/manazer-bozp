"""Parsování textové odpovědi AI na seznam návrhů."""

from __future__ import annotations

import re

from core.ai_oponentni.types import AiProposal

_AREA_RE = re.compile(r"^oblast\s*:\s*(.+)$", re.IGNORECASE)
_NAME_RE = re.compile(r"^návrh\s*:\s*(.+)$", re.IGNORECASE)
_PARENT_RE = re.compile(r"^rodič\s*:\s*(.+)$", re.IGNORECASE)
_REASON_RE = re.compile(r"^zdůvodnění\s*:\s*(.*)$", re.IGNORECASE)


def parse_ai_peer_review_response(text: str) -> list[AiProposal]:
    """
    Očekávaný formát bloku:

    Oblast: ...
    Návrh: ...
    Rodič: ITEM-001   (volitelné)
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
        if parent_raw and parent_raw not in {"—", "-", "–", "null", "None"}:
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
