"""Prezentační model položky panelu Nadcházející události a úkoly."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


ITEM_TYPE_TASK = "task"
ITEM_TYPE_AUDIT = "audit"
ITEM_TYPE_INSPECTION = "inspection"
ITEM_TYPE_MEETING = "meeting"
ITEM_TYPE_PERIODIC = "periodic"
ITEM_TYPE_YEARLY_PLAN_MONTH = "yearly_plan_month"
ITEM_TYPE_OZO_CONTRACT = "ozo_contract"
# Zpětná kompatibilita staršího interního názvu.
ITEM_TYPE_BOZP_INSPECTION = ITEM_TYPE_INSPECTION

TYPE_LABELS = {
    ITEM_TYPE_TASK: "Úkol",
    ITEM_TYPE_AUDIT: "Audit",
    ITEM_TYPE_INSPECTION: "Prověrka",
    ITEM_TYPE_MEETING: "Událost",
    ITEM_TYPE_PERIODIC: "Periodická činnost",
    ITEM_TYPE_YEARLY_PLAN_MONTH: "Roční plán",
    ITEM_TYPE_OZO_CONTRACT: "Smlouva OZO",
}

SOURCE_LABEL_AUDIT = "Audit systému řízení"
SOURCE_LABEL_INSPECTION = "Prověrka BOZP"
SOURCE_LABEL_PERIODIC = "Periodická činnost"
SOURCE_LABEL_YEARLY_PLAN = "Roční plán"
SOURCE_LABEL_OZO_CONTRACT = "Smlouvy OZO"

PRIORITY_RANK = {
    "Kritická": 0,
    "Vysoká": 1,
    "Normální": 2,
    "Nízká": 3,
}


@dataclass(frozen=True)
class AttentionItem:
    item_type: str
    source_id: int
    title: str
    date: date | None
    subtitle: str
    status: str
    source_type: str = ""
    priority: str = ""
    event_at: datetime | None = None
    ends_at: datetime | None = None
    open_metadata: dict[str, Any] = field(default_factory=dict)
    sort_key: tuple = ()

    @property
    def type_label(self) -> str:
        return TYPE_LABELS.get(self.item_type, self.item_type)

    @property
    def entity_id(self) -> int:
        """Zpětná kompatibilita pro starší volání."""
        return self.source_id

    @property
    def due_date(self) -> date | None:
        """Zpětná kompatibilita pro starší volání."""
        return self.date

    @property
    def source_label(self) -> str:
        """Zpětná kompatibilita pro starší volání."""
        return self.subtitle
