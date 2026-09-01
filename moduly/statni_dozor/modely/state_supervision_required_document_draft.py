"""Pracovní kopie požadovaného dokladu — bez Qt a bez zápisu do DB."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


def new_required_document_client_key() -> str:
    return uuid.uuid4().hex


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
    client_key: str = field(default_factory=new_required_document_client_key)
