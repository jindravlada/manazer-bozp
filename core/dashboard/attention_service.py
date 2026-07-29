"""Lehké sestavení položek panelu Nadcházející události a úkoly."""

from __future__ import annotations

from datetime import date

from core.dashboard.attention_item import (
    ITEM_TYPE_AUDIT,
    ITEM_TYPE_INSPECTION,
    ITEM_TYPE_TASK,
    SOURCE_LABEL_AUDIT,
    SOURCE_LABEL_INSPECTION,
    AttentionItem,
)
from core.shared.task_source_display import task_source_short_label
from moduly.audity.sluzby.audit_service import audit_service
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.ukoly.sluzby.task_service import task_service


def build_sort_key(
    due_date: date | None,
    *,
    item_type: str = "",
    title: str = "",
    source_id: int = 0,
    today: date | None = None,
) -> tuple:
    """Řazení: datum vzestupně, potom typ, název, source_id."""
    if due_date is None:
        date_key = date.max
    else:
        date_key = due_date

    return (
        date_key,
        (item_type or "").casefold(),
        (title or "").casefold(),
        int(source_id),
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
                source_type=ITEM_TYPE_TASK,
                source_id=task.id,
                title=title,
                date=task.due_date,
                subtitle=_task_source_label(task),
                status=task.computed_status or "",
                priority=priority,
                open_metadata={"source_type": ITEM_TYPE_TASK, "source_id": task.id},
                sort_key=build_sort_key(
                    task.due_date,
                    item_type=ITEM_TYPE_TASK,
                    title=title,
                    source_id=task.id,
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


def _from_audits(_today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for audit in audit_service.get_all():
        due_date = audit.started_at
        if due_date is None:
            continue
        if audit.finished_at is not None:
            continue
        title = audit_title(audit)
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_AUDIT,
                source_type=ITEM_TYPE_AUDIT,
                source_id=audit.id,
                title=title,
                date=due_date,
                subtitle=SOURCE_LABEL_AUDIT,
                status=audit.status or "",
                priority="",
                open_metadata={"source_type": ITEM_TYPE_AUDIT, "source_id": audit.id},
                sort_key=build_sort_key(
                    due_date,
                    item_type=ITEM_TYPE_AUDIT,
                    title=title,
                    source_id=audit.id,
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


def _from_inspections(_today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for inspection in bozp_inspection_service.get_all():
        due_date = inspection.started_at
        if due_date is None:
            continue
        if inspection.finished_at is not None:
            continue
        title = inspection_title(inspection)
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_INSPECTION,
                source_type=ITEM_TYPE_INSPECTION,
                source_id=inspection.id,
                title=title,
                date=due_date,
                subtitle=SOURCE_LABEL_INSPECTION,
                status=inspection.status or "",
                priority="",
                open_metadata={
                    "source_type": ITEM_TYPE_INSPECTION,
                    "source_id": inspection.id,
                },
                sort_key=build_sort_key(
                    due_date,
                    item_type=ITEM_TYPE_INSPECTION,
                    title=title,
                    source_id=inspection.id,
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
