"""Read-only posouzení, zda uzavření kontroly má nevyřešená zjištění nebo úkoly."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from core.shared.constants import FINDING_STATUS_VYPORADANO
from moduly.ukoly.constants import TASK_STATUS_CANCELED, TASK_STATUS_CLOSED

_TERMINAL_TASK_STATUSES = frozenset({TASK_STATUS_CLOSED, TASK_STATUS_CANCELED})


@dataclass(frozen=True)
class StateSupervisionClosureReadiness:
    """Souhrn nevyřešených položek před přechodem do stavu Uzavřena."""

    open_findings_count: int = 0
    active_tasks_count: int = 0
    missing_tasks_count: int = 0
    open_finding_keys: tuple[str, ...] = ()
    active_task_ids: tuple[int, ...] = ()
    missing_task_ids: tuple[int, ...] = ()

    @property
    def needs_confirmation(self) -> bool:
        return (
            self.open_findings_count > 0
            or self.active_tasks_count > 0
            or self.missing_tasks_count > 0
        )


def _draft_key(draft: Any) -> str:
    client_key = getattr(draft, "client_key", None)
    if client_key:
        return str(client_key)
    finding_id = getattr(draft, "id", None)
    if finding_id is not None:
        return f"id-{int(finding_id)}"
    return ""


def _load_tasks_by_ids(task_ids: Sequence[int]) -> Sequence[Any]:
    from moduly.ukoly.sluzby.task_service import task_service

    return task_service.get_tasks_by_ids(list(task_ids))


def state_supervision_closure_readiness(
    drafts: Sequence[Any],
    *,
    load_tasks: Callable[[Sequence[int]], Sequence[Any]] | None = None,
) -> StateSupervisionClosureReadiness:
    """Spočítá otevřená zjištění, neukončené úkoly a chybějící vazby.

    Nic nezapisuje. Úkoly načítá dávkově podle ``task_id`` pracovních draftů.
    """
    open_keys: list[str] = []
    task_ids: list[int] = []
    seen_task_ids: set[int] = set()
    for draft in drafts:
        status = str(getattr(draft, "status", "") or "").strip()
        if status != FINDING_STATUS_VYPORADANO:
            open_keys.append(_draft_key(draft))
        task_id = getattr(draft, "task_id", None)
        if task_id is None:
            continue
        numeric = int(task_id)
        if numeric in seen_task_ids:
            continue
        seen_task_ids.add(numeric)
        task_ids.append(numeric)

    loader = load_tasks if load_tasks is not None else _load_tasks_by_ids
    loaded = loader(task_ids) if task_ids else []
    by_id = {
        int(task.id): task
        for task in loaded
        if getattr(task, "id", None) is not None
    }
    active_ids: list[int] = []
    missing_ids: list[int] = []
    for task_id in task_ids:
        task = by_id.get(task_id)
        if task is None:
            missing_ids.append(task_id)
            continue
        status = str(getattr(task, "computed_status", "") or "")
        if status not in _TERMINAL_TASK_STATUSES:
            active_ids.append(task_id)

    return StateSupervisionClosureReadiness(
        open_findings_count=len(open_keys),
        active_tasks_count=len(active_ids),
        missing_tasks_count=len(missing_ids),
        open_finding_keys=tuple(open_keys),
        active_task_ids=tuple(active_ids),
        missing_task_ids=tuple(missing_ids),
    )
