"""Lehké sestavení položek panelu Nadcházející události a úkoly."""

from __future__ import annotations

from datetime import date, datetime, time

from core.dashboard.attention_item import (
    ITEM_TYPE_AUDIT,
    ITEM_TYPE_INSPECTION,
    ITEM_TYPE_MEETING,
    ITEM_TYPE_TASK,
    SOURCE_LABEL_AUDIT,
    SOURCE_LABEL_INSPECTION,
    AttentionItem,
)
from core.shared.task_source_display import task_source_short_label
from moduly.audity.sluzby.audit_service import audit_service
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.schuzky.constants import STATUS_PLANNED
from moduly.schuzky.sluzby.meeting_service import meeting_service
from moduly.ukoly.sluzby.task_service import task_service


def build_sort_key(
    due_date: date | None,
    *,
    item_type: str = "",
    title: str = "",
    source_id: int = 0,
    today: date | None = None,
    due_datetime: datetime | None = None,
) -> tuple:
    """Řazení: datum/čas vzestupně, potom typ, název, source_id."""
    if due_datetime is not None:
        dt_key = due_datetime
    elif due_date is None:
        dt_key = datetime.max
    else:
        dt_key = datetime.combine(due_date, time.min)

    return (
        dt_key,
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


def _meeting_subtitle(meeting) -> str:
    parts: list[str] = []
    location = (meeting.location or "").strip()
    organizer = (meeting.organizer_name or "").strip()
    if location:
        parts.append(location)
    if organizer:
        parts.append(organizer)
    return " · ".join(parts)


def _from_meetings(_today: date) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    for meeting in meeting_service.get_all():
        if (meeting.status or "") != STATUS_PLANNED:
            continue
        starts_at = meeting.starts_at
        if starts_at is None:
            continue
        title = (meeting.title or "").strip() or f"Událost #{meeting.id}"
        event_type = (getattr(meeting, "event_type", None) or "").strip()
        if event_type:
            title = f"{event_type} – {title}"
        ends_at = meeting.ends_at
        items.append(
            AttentionItem(
                item_type=ITEM_TYPE_MEETING,
                source_type=ITEM_TYPE_MEETING,
                source_id=meeting.id,
                title=title,
                date=starts_at.date(),
                subtitle=_meeting_subtitle(meeting),
                status=meeting.status or "",
                priority="",
                event_at=starts_at,
                ends_at=ends_at,
                open_metadata={
                    "source_type": ITEM_TYPE_MEETING,
                    "source_id": meeting.id,
                },
                sort_key=build_sort_key(
                    starts_at.date(),
                    item_type=ITEM_TYPE_MEETING,
                    title=title,
                    source_id=meeting.id,
                    due_datetime=starts_at,
                ),
            )
        )
    return items


def get_attention_items(*, today: date | None = None) -> list[AttentionItem]:
    """Vrátí společně seřazené úkoly, audity, prověrky a schůzky."""
    today = today or date.today()
    items = (
        _from_tasks(today)
        + _from_audits(today)
        + _from_inspections(today)
        + _from_meetings(today)
    )
    items.sort(key=lambda item: item.sort_key)
    return items
