"""Společné mapování termínů Státního dozoru na AttentionItem (6B2/6B3)."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from core.dashboard.attention_item import (
    ITEM_TYPE_STATE_SUPERVISION,
    SOURCE_LABEL_STATE_SUPERVISION,
    AttentionItem,
)


def _sort_key(
    due_date: date | None,
    *,
    title: str,
    source_id: int,
    due_datetime: datetime | None,
) -> tuple:
    if due_datetime is not None:
        dt_key = due_datetime
    elif due_date is None:
        dt_key = datetime.max
    else:
        dt_key = datetime.combine(due_date, time.min)
    return (
        dt_key,
        ITEM_TYPE_STATE_SUPERVISION.casefold(),
        (title or "").casefold(),
        int(source_id),
    )


def attention_item_from_state_supervision_deadline(projected: Any) -> AttentionItem:
    """Jedno mapování StateSupervisionDeadlineItem → AttentionItem."""
    supervision_id = int(projected.supervision_id)
    metadata: dict[str, Any] = {
        "kind": projected.kind,
        "target_tab": projected.target_tab,
        "supervision_id": supervision_id,
    }
    if getattr(projected, "child_id", None) is not None:
        metadata["child_id"] = int(projected.child_id)
    title = str(projected.title or "")
    due_date = projected.due_date
    event_at = projected.event_at
    return AttentionItem(
        item_type=ITEM_TYPE_STATE_SUPERVISION,
        source_type=ITEM_TYPE_STATE_SUPERVISION,
        source_id=supervision_id,
        title=title,
        date=due_date,
        subtitle=SOURCE_LABEL_STATE_SUPERVISION,
        status="",
        priority=str(projected.priority or ""),
        event_at=event_at,
        open_metadata=metadata,
        sort_key=_sort_key(
            due_date,
            title=title,
            source_id=supervision_id,
            due_datetime=event_at,
        ),
        detail_tooltip=str(getattr(projected, "detail", "") or ""),
        identity_key=str(projected.identity_key or ""),
        type_label_override=str(projected.type_label or "") or None,
    )


def deadline_item_belongs_in_attention(projected: Any, today: date) -> bool:
    """Nadcházející: upcoming, plus prošlé reminder položky kvůli kartě Po termínu."""
    if bool(getattr(projected, "include_in_upcoming", False)):
        return True
    if not bool(getattr(projected, "include_in_reminders", False)):
        return False
    due = getattr(projected, "due_date", None)
    return due is not None and due < today


def deadline_item_belongs_in_reminders(projected: Any, today: date) -> bool:
    """Připomínky: od due_date včetně dneška."""
    if not bool(getattr(projected, "include_in_reminders", False)):
        return False
    due = getattr(projected, "due_date", None)
    return due is not None and due <= today
