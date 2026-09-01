"""Pracovní kopie zjištění kontroly státního dozoru — bez Qt a bez zápisu do DB."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from core.shared.constants import FINDING_STATUS_OTEVRENE, FINDING_TYPE_ZJISTENI


def new_finding_client_key() -> str:
    return uuid.uuid4().hex


@dataclass
class StateSupervisionFindingDraft:
    """Draft zjištění mapovaný na existující model ``Finding``.

    ``client_key`` je stabilní pracovní identita nového draftu bez DB ID.
    ``source_area_label`` je volitelné místo / oblast. ``task_id`` se pouze
    zachovává — služba z něj úkol nevytváří.
    """

    finding_type: str = FINDING_TYPE_ZJISTENI
    description: str = ""
    id: int | None = None
    source_area_label: str = ""
    status: str = FINDING_STATUS_OTEVRENE
    responsible_person_id: int | None = None
    responsible_person_name: str = ""
    due_date: date | None = None
    recommended_action: str = ""
    resolution_note: str = ""
    resolved_at: date | None = None
    task_id: int | None = None
    display_order: int = 0
    client_key: str = field(default_factory=new_finding_client_key)
