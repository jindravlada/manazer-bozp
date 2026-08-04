"""Úkoly ze závěrů jednání schůzky."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from core.shared.constants import ENTITY_MEETING
from moduly.schuzky.constants import CONCLUSION_CHECK_PREFIX
from moduly.ukoly.modely.task import Task
from moduly.ukoly.sluzby.task_service import task_service


def split_conclusion_lines(text: str | None) -> list[str]:
    """Rozdělí závěry podle Enterů; prázdné řádky přeskočí, pořadí zachová."""
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line:
            lines.append(line)
    return lines


def conclusion_check_code(line: str) -> str:
    """Stabilní kód bodu závěru (nezávislý na pořadí řádku)."""
    normalized = (line or "").strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{CONCLUSION_CHECK_PREFIX}{digest}"[:100]


@dataclass(frozen=True)
class ConclusionTaskRow:
    text: str
    check_code: str
    task: Task | None = None


@dataclass(frozen=True)
class ConclusionTaskView:
    rows: list[ConclusionTaskRow]
    orphan_tasks: list[Task]


def list_meeting_tasks(meeting_id: int) -> list[Task]:
    return task_service.repository.list_by_source(
        source_module=ENTITY_MEETING,
        source_record_id=int(meeting_id),
    )


def build_conclusion_task_view(
    conclusions_text: str | None,
    *,
    meeting_id: int | None,
) -> ConclusionTaskView:
    lines = split_conclusion_lines(conclusions_text)
    tasks = list_meeting_tasks(meeting_id) if meeting_id is not None else []

    by_code: dict[str, list[Task]] = {}
    for task in tasks:
        code = (task.source_check_code or "").strip()
        if not code.startswith(CONCLUSION_CHECK_PREFIX):
            continue
        by_code.setdefault(code, []).append(task)

    used_ids: set[int] = set()
    rows: list[ConclusionTaskRow] = []
    for line in lines:
        code = conclusion_check_code(line)
        task = None
        candidates = by_code.get(code) or []
        for candidate in candidates:
            if candidate.id in used_ids:
                continue
            task = candidate
            used_ids.add(candidate.id)
            break
        rows.append(ConclusionTaskRow(text=line, check_code=code, task=task))

    orphans = [task for task in tasks if task.id not in used_ids]
    return ConclusionTaskView(rows=rows, orphan_tasks=orphans)
