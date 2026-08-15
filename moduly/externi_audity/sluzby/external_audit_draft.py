"""Pracovní kopie externího auditu (EA-1) — bez zápisu do DB."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


def new_client_key() -> str:
    return uuid.uuid4().hex


@dataclass
class ParticipantDraft:
    client_key: str
    role: str
    source_type: str
    source_id: int
    display_name_snapshot: str
    display_order: int = 0
    db_id: int | None = None


@dataclass
class VisitDraft:
    client_key: str
    visit_date: date
    workplace_id: int
    workplace_name_snapshot: str
    workplace_address_snapshot: str
    time_from: str | None = None
    time_to: str | None = None
    note: str | None = None
    display_order: int = 0
    participant_keys: list[str] = field(default_factory=list)
    db_id: int | None = None


@dataclass
class FindingDraft:
    client_key: str
    finding_type: str
    description: str
    status: str
    due_date: date | None = None
    resolution_text: str | None = None
    resolved_at: datetime | None = None
    display_order: int = 0
    db_id: int | None = None
    # Jen pro UI snapshot navázaných úkolů (neukládá se v save_bundle)
    linked_task_ids: list[int] = field(default_factory=list)


@dataclass
class AttachmentStagingState:
    """Odložené přílohy — fyzika/DB až při hlavním Uložit."""

    pending_add_paths: list[str] = field(default_factory=list)
    pending_remove_ids: list[int] = field(default_factory=list)

    def clear(self) -> None:
        self.pending_add_paths.clear()
        self.pending_remove_ids.clear()

    def has_changes(self) -> bool:
        return bool(self.pending_add_paths or self.pending_remove_ids)


@dataclass
class ExternalAuditDraft:
    audit_id: int | None
    audit_type: str
    status: str
    organization_ico: str
    organization_name: str
    organization_address: str
    remind_from: date | None = None
    note: str | None = None
    organization_extra: dict[str, Any] = field(default_factory=dict)
    participants: list[ParticipantDraft] = field(default_factory=list)
    visits: list[VisitDraft] = field(default_factory=list)
    findings: list[FindingDraft] = field(default_factory=list)
    attachments: AttachmentStagingState = field(default_factory=AttachmentStagingState)

    def derived_date_range(self) -> tuple[date | None, date | None]:
        if not self.visits:
            return None, None
        dates = [visit.visit_date for visit in self.visits]
        return min(dates), max(dates)

    def participant_by_key(self, key: str) -> ParticipantDraft | None:
        for item in self.participants:
            if item.client_key == key:
                return item
        return None

    def participants_for_role(self, role: str) -> list[ParticipantDraft]:
        return [item for item in self.participants if item.role == role]

    def findings_for_type(self, finding_type: str) -> list[FindingDraft]:
        return [item for item in self.findings if item.finding_type == finding_type]

    def finding_by_key(self, key: str) -> FindingDraft | None:
        for item in self.findings:
            if item.client_key == key:
                return item
        return None
