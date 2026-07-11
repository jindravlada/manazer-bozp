"""Lehké sestavení položek panelu Vyžaduje pozornost z existujících dat."""

from __future__ import annotations

from datetime import date

from core.dashboard.attention_item import (
    ITEM_TYPE_AUDIT,
    ITEM_TYPE_BOZP_INSPECTION,
    ITEM_TYPE_TASK,
    PRIORITY_RANK,
    SOURCE_LABEL_AUDIT,
    SOURCE_LABEL_INSPECTION,
    AttentionItem,
)
from core.shared.task_source_display import task_source_short_label
from moduly.audity.constants import AUDIT_STATUS_DOKONCENO
from moduly.audity.sluzby.audit_service import audit_service
from moduly.proverky.constants import INSPECTION_STATUS_DOKONCENO
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.ukoly.sluzby.task_service import task_service


def build_sort_key(
    due_date: date | None,
    *,
    priority: str = "",
    title: str = "",
    today: date | None = None,
) -> tuple:
    """Řazení: po termínu → dnes → budoucí → bez termínu; pak priorita, název."""
    today = today or date.today()
    if due_date is None:
        bucket = 3
        date_key = date.max
    elif due_date < today:
        bucket = 0
        date_key = due_date
    elif due_date == today:
        bucket = 1
        date_key = due_date
    else:
        bucket = 2
        date_key = due_date

    return (
        bucket,
        date_key,
        PRIORITY_RANK.get(priority, 4),
        (title or "").casefold(),
    )


def _task_source_label(task) -> str:
    label = (task_source_short_label(task) or "").strip()
    if not label or label == "—":
        return ""
    return label


def _from_tasks(today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for task in task_service.get_all_tasks():
        if task.computed_status in ("Ukončeno", "Zrušeno"):
            continue
        title = (task.title or "").strip() or f"Úkol #{task.id}"
        priority = task.priority or ""
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_TASK,
                entity_id=task.id,
                title=title,
                due_date=task.due_date,
                source_label=_task_source_label(task),
                status=task.computed_status or "",
                priority=priority,
                open_metadata={"item_type": ITEM_TYPE_TASK, "entity_id": task.id},
                sort_key=build_sort_key(
                    task.due_date,
                    priority=priority,
                    title=title,
                    today=today,
                ),
            )
        )
    return items


def audit_title(audit) -> str:
    place = (audit.workplace_name or "").strip()
    if place:
        return f"Audit – {place}"
    number = (audit.number or "").strip()
    if number:
        return f"Audit – {number}"
    title = (audit.title or "").strip()
    if title:
        return f"Audit – {title}"
    return f"Audit #{audit.id}"


def audit_attention_due_date(audit) -> date | None:
    """Termín pro pozornost: po zahájení Datum zahájení, jinak plánovaný termín."""
    if audit.started_at is not None:
        return audit.started_at
    return audit.audit_date


def _from_audits(today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for audit in audit_service.get_all():
        if audit.status == AUDIT_STATUS_DOKONCENO or audit.finished_at is not None:
            continue
        due_date = audit_attention_due_date(audit)
        if due_date is None:
            continue
        title = audit_title(audit)
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_AUDIT,
                entity_id=audit.id,
                title=title,
                due_date=due_date,
                source_label=SOURCE_LABEL_AUDIT,
                status=audit.status or "",
                priority="",
                open_metadata={"item_type": ITEM_TYPE_AUDIT, "entity_id": audit.id},
                sort_key=build_sort_key(
                    due_date,
                    title=title,
                    today=today,
                ),
            )
        )
    return items


def inspection_title(inspection) -> str:
    place = (inspection.workplace_name or "").strip()
    if place:
        return f"Prověrka BOZP – {place}"
    number = (inspection.number or "").strip()
    if number:
        return f"Prověrka BOZP – {number}"
    title = (inspection.title or "").strip()
    if title:
        return f"Prověrka BOZP – {title}"
    return f"Prověrka BOZP #{inspection.id}"


def inspection_attention_due_date(inspection) -> date | None:
    """Termín pro pozornost: po zahájení Datum zahájení, jinak plánovaný termín."""
    if inspection.started_at is not None:
        return inspection.started_at
    return inspection.inspection_date


def _from_inspections(today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for inspection in bozp_inspection_service.get_all():
        if (
            inspection.status == INSPECTION_STATUS_DOKONCENO
            or inspection.finished_at is not None
        ):
            continue
        due_date = inspection_attention_due_date(inspection)
        if due_date is None:
            continue
        title = inspection_title(inspection)
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_BOZP_INSPECTION,
                entity_id=inspection.id,
                title=title,
                due_date=due_date,
                source_label=SOURCE_LABEL_INSPECTION,
                status=inspection.status or "",
                priority="",
                open_metadata={
                    "item_type": ITEM_TYPE_BOZP_INSPECTION,
                    "entity_id": inspection.id,
                },
                sort_key=build_sort_key(
                    due_date,
                    title=title,
                    today=today,
                ),
            )
        )
    return items


def get_attention_items(*, today: date | None = None) -> list[AttentionItem]:
    """Vrátí společně seřazené úkoly, audity a prověrky vyžadující pozornost."""
    today = today or date.today()
    items = _from_tasks(today) + _from_audits(today) + _from_inspections(today)
    items.sort(key=lambda item: item.sort_key)
    return items
