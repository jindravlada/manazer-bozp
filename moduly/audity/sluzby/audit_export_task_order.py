"""Exportní pořadí a čísla úkolů podle zjištění interního auditu."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from core.shared.constants import ENTITY_AUDITY, ENTITY_FINDING
from core.shared.modely.finding import Finding
from moduly.ukoly.modely.task import Task
from moduly.ukoly.sluzby.task_service import task_service


@dataclass(frozen=True)
class AuditExportTaskItem:
    task: Task
    export_number: int
    related_finding_numbers: tuple[int, ...]


def ordered_audit_export_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Stejné pořadí jako číslování zjištění v Protokolu / Podrobné zprávě."""
    return sorted(
        findings,
        key=lambda item: (int(item.display_order or 0), int(item.id)),
    )


def finding_export_number_map(findings: Sequence[Finding]) -> dict[int, int]:
    return {
        int(finding.id): index
        for index, finding in enumerate(ordered_audit_export_findings(findings), start=1)
    }


def _task_sort_key(task: Task) -> tuple:
    return (task.due_date or date.max, int(task.id))


def build_audit_export_task_items(
    *,
    ordered_findings: Sequence[Finding],
    tasks_by_id: Mapping[int, Task],
    source_tasks_by_finding_id: Mapping[int, Sequence[Task]],
    unlinked_tasks: Sequence[Task],
) -> list[AuditExportTaskItem]:
    """Sestaví souvislou řadu 1…N. Jeden úkol jen jednou."""
    number_by_finding_id = {
        int(finding.id): index
        for index, finding in enumerate(ordered_findings, start=1)
    }
    finding_ids_by_task_id: dict[int, list[int]] = {}
    tasks_by_finding_id: dict[int, list[Task]] = {
        int(finding.id): [] for finding in ordered_findings
    }

    def _attach(finding_id: int, task: Task) -> None:
        task_id = int(task.id)
        finding_ids_by_task_id.setdefault(task_id, [])
        if finding_id not in finding_ids_by_task_id[task_id]:
            finding_ids_by_task_id[task_id].append(finding_id)
        bucket = tasks_by_finding_id.setdefault(finding_id, [])
        if all(int(existing.id) != task_id for existing in bucket):
            bucket.append(task)

    for finding in ordered_findings:
        finding_id = int(finding.id)
        task_id = getattr(finding, "task_id", None)
        if task_id:
            task = tasks_by_id.get(int(task_id))
            if task is not None:
                _attach(finding_id, task)
        for task in source_tasks_by_finding_id.get(finding_id, ()):
            _attach(finding_id, task)

    placed: set[int] = set()
    ordered_tasks: list[tuple[Task, tuple[int, ...]]] = []

    for finding in ordered_findings:
        finding_id = int(finding.id)
        group = sorted(tasks_by_finding_id.get(finding_id, ()), key=_task_sort_key)
        for task in group:
            task_id = int(task.id)
            if task_id in placed:
                continue
            related = tuple(
                sorted(
                    number_by_finding_id[fid]
                    for fid in finding_ids_by_task_id.get(task_id, ())
                    if fid in number_by_finding_id
                )
            )
            ordered_tasks.append((task, related))
            placed.add(task_id)

    extras = [task for task in unlinked_tasks if int(task.id) not in placed]
    extras.sort(key=_task_sort_key)
    for task in extras:
        related = tuple(
            sorted(
                number_by_finding_id[fid]
                for fid in finding_ids_by_task_id.get(int(task.id), ())
                if fid in number_by_finding_id
            )
        )
        ordered_tasks.append((task, related))
        placed.add(int(task.id))

    return [
        AuditExportTaskItem(
            task=task,
            export_number=index,
            related_finding_numbers=related,
        )
        for index, (task, related) in enumerate(ordered_tasks, start=1)
    ]


def load_audit_export_task_items(
    audit_id: int,
    *,
    findings: Sequence[Finding],
) -> list[AuditExportTaskItem]:
    """Načte úkoly hromadně (bez N+1) a sestaví exportní pořadí."""
    ordered = ordered_audit_export_findings(findings)
    finding_ids = [int(finding.id) for finding in ordered]
    linked_ids = [
        int(finding.task_id)
        for finding in ordered
        if getattr(finding, "task_id", None)
    ]

    linked_tasks = task_service.get_tasks_by_ids(linked_ids)
    source_tasks = task_service.list_by_sources(ENTITY_FINDING, finding_ids)
    audit_tasks = task_service.list_by_source(ENTITY_AUDITY, int(audit_id))

    tasks_by_id: dict[int, Task] = {}
    for task in (*linked_tasks, *source_tasks, *audit_tasks):
        tasks_by_id.setdefault(int(task.id), task)

    source_tasks_by_finding_id: dict[int, list[Task]] = {}
    for task in source_tasks:
        source_id = getattr(task, "source_record_id", None)
        if source_id is None:
            continue
        source_tasks_by_finding_id.setdefault(int(source_id), []).append(task)

    return build_audit_export_task_items(
        ordered_findings=ordered,
        tasks_by_id=tasks_by_id,
        source_tasks_by_finding_id=source_tasks_by_finding_id,
        unlinked_tasks=audit_tasks,
    )
