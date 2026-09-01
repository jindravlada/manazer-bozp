"""Pracovní kopie záznamu průběhu kontroly — bez Qt a bez zápisu do DB."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


def new_timeline_item_client_key() -> str:
    return uuid.uuid4().hex


@dataclass
class StateSupervisionTimelineItemDraft:
    title: str
    id: int | None = None
    occurred_at: datetime | None = None
    place: str | None = None
    notes: str | None = None
    display_order: int = 0
    active: bool = True
    client_key: str = field(default_factory=new_timeline_item_client_key)
