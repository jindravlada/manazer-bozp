"""Prezentační model položky panelu Vyžaduje pozornost (bez DB tabulky)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


ITEM_TYPE_TASK = "task"
ITEM_TYPE_AUDIT = "audit"
ITEM_TYPE_BOZP_INSPECTION = "bozp_inspection"

TYPE_LABELS = {
    ITEM_TYPE_TASK: "Úkol",
    ITEM_TYPE_AUDIT: "Audit",
    ITEM_TYPE_BOZP_INSPECTION: "Prověrka",
}

SOURCE_LABEL_AUDIT = "Audit systému řízení"
SOURCE_LABEL_INSPECTION = "Prověrka BOZP"

PRIORITY_RANK = {
    "Kritická": 0,
    "Vysoká": 1,
    "Normální": 2,
    "Nízká": 3,
}


@dataclass(frozen=True)
class AttentionItem:
    item_type: str
    entity_id: int
    title: str
    due_date: date | None
    source_label: str
    status: str
    priority: str = ""
    open_metadata: dict[str, Any] = field(default_factory=dict)
    sort_key: tuple = ()

    @property
    def type_label(self) -> str:
        return TYPE_LABELS.get(self.item_type, self.item_type)
