"""Pracovní kopie požadovaného dokladu — bez Qt a bez zápisu do DB."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class StateSupervisionRequiredDocumentDraft:
    title: str
    id: int | None = None
    responsible_source_type: str | None = None
    responsible_source_id: int | None = None
    responsible_name_snapshot: str | None = None
    due_at: datetime | None = None
    prepared_at: datetime | None = None
    submitted_at: datetime | None = None
    note: str | None = None
    display_order: int = 0
    active: bool = True
