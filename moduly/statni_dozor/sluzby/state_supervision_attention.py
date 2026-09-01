"""Read-only upozornění přehledu Státního dozoru — bez zápisu a bez změny statusu."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from core.shared.constants import ENTITY_STATE_SUPERVISION, FINDING_STATUS_VYPORADANO
from moduly.statni_dozor.constants import (
    ATTENTION_REASON_MISSING_TASKS,
    ATTENTION_REASON_OVERDUE_DOCUMENTS,
    ATTENTION_REASON_OVERDUE_FINDINGS,
    ATTENTION_REASON_OVERDUE_OBJECTIONS,
    ATTENTION_REASON_OVERDUE_PLANNED_START,
    ATTENTION_REASON_OVERDUE_TASKS,
    STATUS_CANCELLED,
    STATUS_CLOSED,
)
from moduly.ukoly.constants import TASK_STATUS_CANCELED, TASK_STATUS_CLOSED
from moduly.ukoly.sluzby.task_deadline import task_urgency_due_date

_TERMINAL_TASK_STATUSES = frozenset({TASK_STATUS_CLOSED, TASK_STATUS_CANCELED})
_CLOSED_SUPERVISION_STATUSES = frozenset({STATUS_CLOSED, STATUS_CANCELLED})


@dataclass(frozen=True)
class AttentionReason:
    """Strukturovaný důvod upozornění, nezávislý na textu tooltipu."""

    code: str
    count: int = 0


@dataclass(frozen=True)
class StateSupervisionAttention:
    """Souhrn aktuálních upozornění jedné kontroly."""

    has_alert: bool = False
    reasons: tuple[AttentionReason, ...] = ()
    overdue_documents_count: int = 0
    overdue_findings_count: int = 0
    overdue_tasks_count: int = 0
    missing_tasks_count: int = 0
    overdue_objections: bool = False
    overdue_planned_start: bool = False


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return None


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _datetime_overdue(value: Any, now: datetime) -> bool:
    stamp = _as_datetime(value)
    return stamp is not None and stamp < now


def _date_overdue(value: Any, today: date) -> bool:
    day = _as_date(value)
    return day is not None and day < today


def _is_active_document(document: Any) -> bool:
    return bool(getattr(document, "active", True))


def _finding_status(finding: Any) -> str:
    return str(getattr(finding, "status", "") or "").strip()


def attention_for_supervision(
    record: Any,
    *,
    documents: Sequence[Any] = (),
    findings: Sequence[Any] = (),
    tasks_by_id: Mapping[int, Any] | None = None,
    now: datetime,
) -> StateSupervisionAttention:
    """Spočítá upozornění jedné kontroly z už předaných kolekcí. Nic nezapisuje."""
    today = now.date()
    loaded_tasks = tasks_by_id or {}

    overdue_documents = 0
    for document in documents:
        if not _is_active_document(document):
            continue
        if getattr(document, "submitted_at", None) is not None:
            continue
        if _datetime_overdue(getattr(document, "due_at", None), now):
            overdue_documents += 1

    overdue_findings = 0
    task_ids: list[int] = []
    seen_task_ids: set[int] = set()
    for finding in findings:
        if _finding_status(finding) != FINDING_STATUS_VYPORADANO:
            if _date_overdue(getattr(finding, "due_date", None), today):
                overdue_findings += 1
        task_id = getattr(finding, "task_id", None)
        if task_id is None:
            continue
        numeric = int(task_id)
        if numeric in seen_task_ids:
            continue
        seen_task_ids.add(numeric)
        task_ids.append(numeric)

    overdue_tasks = 0
    missing_tasks = 0
    for task_id in task_ids:
        task = loaded_tasks.get(task_id)
        if task is None:
            missing_tasks += 1
            continue
        status = str(getattr(task, "computed_status", "") or "")
        if status in _TERMINAL_TASK_STATUSES:
            continue
        decisive = task_urgency_due_date(task)
        if _date_overdue(decisive, today):
            overdue_tasks += 1

    overdue_objections = _datetime_overdue(
        getattr(record, "objections_due_at", None),
        now,
    ) and getattr(record, "objections_submitted_at", None) is None

    status = str(getattr(record, "status", "") or "")
    overdue_planned_start = (
        status not in _CLOSED_SUPERVISION_STATUSES
        and getattr(record, "started_at", None) is None
        and _datetime_overdue(getattr(record, "planned_start_at", None), now)
    )

    reasons: list[AttentionReason] = []
    if overdue_documents:
        reasons.append(
            AttentionReason(ATTENTION_REASON_OVERDUE_DOCUMENTS, overdue_documents)
        )
    if overdue_findings:
        reasons.append(
            AttentionReason(ATTENTION_REASON_OVERDUE_FINDINGS, overdue_findings)
        )
    if overdue_tasks:
        reasons.append(AttentionReason(ATTENTION_REASON_OVERDUE_TASKS, overdue_tasks))
    if missing_tasks:
        reasons.append(AttentionReason(ATTENTION_REASON_MISSING_TASKS, missing_tasks))
    if overdue_objections:
        reasons.append(AttentionReason(ATTENTION_REASON_OVERDUE_OBJECTIONS, 1))
    if overdue_planned_start:
        reasons.append(AttentionReason(ATTENTION_REASON_OVERDUE_PLANNED_START, 1))

    return StateSupervisionAttention(
        has_alert=bool(reasons),
        reasons=tuple(reasons),
        overdue_documents_count=overdue_documents,
        overdue_findings_count=overdue_findings,
        overdue_tasks_count=overdue_tasks,
        missing_tasks_count=missing_tasks,
        overdue_objections=overdue_objections,
        overdue_planned_start=overdue_planned_start,
    )


def _group_by_supervision_id(rows: Sequence[Any]) -> dict[int, list[Any]]:
    grouped: dict[int, list[Any]] = {}
    for row in rows:
        key = getattr(row, "state_supervision_id", None)
        if key is None:
            key = getattr(row, "entity_id", None)
        if key is None:
            continue
        grouped.setdefault(int(key), []).append(row)
    return grouped


def _default_load_documents(supervision_ids: Sequence[int]) -> Sequence[Any]:
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )

    return state_supervision_required_document_service.list_for_supervisions(
        supervision_ids
    )


def _default_load_findings(supervision_ids: Sequence[int]) -> Sequence[Any]:
    from core.shared.sluzby.finding_service import finding_service

    return finding_service.get_for_entities(
        ENTITY_STATE_SUPERVISION,
        list(supervision_ids),
    )


def _default_load_tasks(task_ids: Sequence[int]) -> Sequence[Any]:
    from moduly.ukoly.sluzby.task_service import task_service

    return task_service.get_tasks_by_ids(list(task_ids))


class StateSupervisionAttentionService:
    """Dávkové read-only vyhodnocení upozornění pro přehled."""

    def summarize(
        self,
        records: Sequence[Any],
        *,
        now: datetime | None = None,
        load_documents: Callable[[Sequence[int]], Sequence[Any]] | None = None,
        load_findings: Callable[[Sequence[int]], Sequence[Any]] | None = None,
        load_tasks: Callable[[Sequence[int]], Sequence[Any]] | None = None,
    ) -> dict[int, StateSupervisionAttention]:
        """Vrátí mapu supervision_id → attention. Nic nezapisuje."""
        ids = [
            int(record.id)
            for record in records
            if getattr(record, "id", None) is not None
        ]
        if not ids:
            return {}
        moment = now if now is not None else datetime.now()
        documents_loader = load_documents or _default_load_documents
        findings_loader = load_findings or _default_load_findings
        tasks_loader = load_tasks or _default_load_tasks

        documents_by_id = _group_by_supervision_id(documents_loader(ids))
        findings_by_id = _group_by_supervision_id(findings_loader(ids))

        task_ids: list[int] = []
        seen_task_ids: set[int] = set()
        for finding_rows in findings_by_id.values():
            for finding in finding_rows:
                task_id = getattr(finding, "task_id", None)
                if task_id is None:
                    continue
                numeric = int(task_id)
                if numeric in seen_task_ids:
                    continue
                seen_task_ids.add(numeric)
                task_ids.append(numeric)
        loaded_tasks = tasks_loader(task_ids) if task_ids else []
        tasks_by_id = {
            int(task.id): task
            for task in loaded_tasks
            if getattr(task, "id", None) is not None
        }

        result: dict[int, StateSupervisionAttention] = {}
        for record in records:
            record_id = getattr(record, "id", None)
            if record_id is None:
                continue
            numeric_id = int(record_id)
            result[numeric_id] = attention_for_supervision(
                record,
                documents=documents_by_id.get(numeric_id, ()),
                findings=findings_by_id.get(numeric_id, ()),
                tasks_by_id=tasks_by_id,
                now=moment,
            )
        return result


state_supervision_attention_service = StateSupervisionAttentionService()
