"""Jednotný řádek měsíčního pohledu Ročního plánu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from moduly.rocni_plan.constants import (
    DISPLAY_PLANNED,
    ROW_KIND_MANUAL,
    ROW_KIND_PERIODIC,
    SOURCE_LABEL_MANUAL,
    SOURCE_LABEL_PERIODIC,
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

    @property
    def is_manual(self) -> bool:
        return self.kind == ROW_KIND_MANUAL

    @property
    def is_periodic(self) -> bool:
        return self.kind == ROW_KIND_PERIODIC
