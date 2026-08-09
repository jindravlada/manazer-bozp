"""Jednotný řádek měsíčního pohledu Ročního plánu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from moduly.rocni_plan.constants import (
    ROW_KIND_MANUAL,
    ROW_KIND_PERIODIC,
)


@dataclass(frozen=True)
class YearlyPlanRow:
    kind: str
    title: str
    note: str
    display_status: str
    link_text: str
    source_label: str
    plan_item_id: int | None = None
    activity_id: int | None = None
    planned_due_date: date | None = None
    occurrence_id: int | None = None
    slot_year: int | None = None
    slot_month: int | None = None
    is_recurring: bool = False

    @property
    def is_manual(self) -> bool:
        return self.kind == ROW_KIND_MANUAL

    @property
    def is_periodic(self) -> bool:
        return self.kind == ROW_KIND_PERIODIC
