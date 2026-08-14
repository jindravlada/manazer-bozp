"""Polymorfní odkazy účastníků Schůzek: person | thp_worker."""

from __future__ import annotations

from typing import Any

MEETING_SOURCE_PERSON = "person"
MEETING_SOURCE_THP_WORKER = "thp_worker"
MEETING_SOURCE_TYPES = frozenset(
    {MEETING_SOURCE_PERSON, MEETING_SOURCE_THP_WORKER}
)


def normalize_participant_ref(item: Any) -> dict[str, Any] | None:
    """Přijme dict {source_type, source_id} nebo legacy int (= person)."""
    if isinstance(item, dict):
        source_type = str(item.get("source_type") or "").strip()
        if source_type not in MEETING_SOURCE_TYPES:
            return None
        try:
            source_id = int(item.get("source_id"))
        except (TypeError, ValueError):
            return None
        if source_id <= 0:
            return None
        return {"source_type": source_type, "source_id": source_id}
    try:
        source_id = int(item)
    except (TypeError, ValueError):
        return None
    if source_id <= 0:
        return None
    return {"source_type": MEETING_SOURCE_PERSON, "source_id": source_id}


def normalize_participant_refs(items: list | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for item in items or []:
        ref = normalize_participant_ref(item)
        if ref is None:
            continue
        key = (ref["source_type"], ref["source_id"])
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result


def ref_key(ref: dict[str, Any] | None) -> tuple[str, int] | None:
    if not ref:
        return None
    try:
        return (str(ref["source_type"]), int(ref["source_id"]))
    except (KeyError, TypeError, ValueError):
        return None
