"""Pracovní kopie účastníka kontroly — bez Qt a bez zápisu do DB."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


def new_participant_client_key() -> str:
    return uuid.uuid4().hex


@dataclass
class StateSupervisionParticipantDraft:
    role: str
    name_snapshot: str = ""
    id: int | None = None
    source_type: str | None = None
    source_id: int | None = None
    organization_snapshot: str | None = None
    contact_note: str | None = None
    planned: bool = True
    attendance_status: str | None = None
    note: str | None = None
    display_order: int = 0
    active: bool = True
    client_key: str = field(default_factory=new_participant_client_key)
