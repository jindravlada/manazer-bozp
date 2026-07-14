"""Rozdělení hierarchických větví do exportních dávek."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_MAX_OBJECTS_PER_BATCH,
    AI_PEER_REVIEW_MAX_SOURCES_PER_BATCH,
)


@dataclass
class ExportBranch:
    """Jedna hierarchie od zdroje analýzy včetně počtu objektů."""

    source_id: int
    source_name: str
    object_count: int
    node: dict
    recommended_limit_exceeded: bool = False


@dataclass
class ExportBatchPlan:
    batch_number: int
    branches: list[ExportBranch] = field(default_factory=list)

    @property
    def source_count(self) -> int:
        return len(self.branches)

    @property
    def object_count(self) -> int:
        return sum(branch.object_count for branch in self.branches)

    @property
    def recommended_limit_exceeded(self) -> bool:
        return any(branch.recommended_limit_exceeded for branch in self.branches)

    @property
    def source_names(self) -> list[str]:
        return [branch.source_name for branch in self.branches]


def count_hierarchy_objects(item_node: dict) -> int:
    total = 1
    for event in item_node.get("events") or []:
        total += 1
        for assessment in event.get("assessments") or []:
            total += 1
            total += len(assessment.get("existing_measures") or [])
            total += len(assessment.get("required_measures") or [])
    return total


def plan_export_batches(
    branches: list[ExportBranch],
    *,
    max_sources: int = AI_PEER_REVIEW_MAX_SOURCES_PER_BATCH,
    max_objects: int = AI_PEER_REVIEW_MAX_OBJECTS_PER_BATCH,
) -> list[ExportBatchPlan]:
    """
    Seskupí větve do dávek. Větev se nikdy nerozdělí.
    Nadlimitní jediná větev tvoří samostatnou dávku.
    """
    if not branches:
        return []

    plans: list[ExportBatchPlan] = []
    current: list[ExportBranch] = []
    current_objects = 0

    def flush() -> None:
        nonlocal current, current_objects
        if current:
            plans.append(ExportBatchPlan(batch_number=0, branches=list(current)))
            current = []
            current_objects = 0

    for branch in branches:
        marked = ExportBranch(
            source_id=branch.source_id,
            source_name=branch.source_name,
            object_count=branch.object_count,
            node=branch.node,
            recommended_limit_exceeded=branch.object_count > max_objects,
        )
        if marked.recommended_limit_exceeded:
            flush()
            plans.append(ExportBatchPlan(batch_number=0, branches=[marked]))
            continue

        would_exceed_sources = len(current) + 1 > max_sources
        would_exceed_objects = current_objects + marked.object_count > max_objects
        if current and (would_exceed_sources or would_exceed_objects):
            flush()

        current.append(marked)
        current_objects += marked.object_count

    flush()

    for index, plan in enumerate(plans, start=1):
        plan.batch_number = index
    return plans
