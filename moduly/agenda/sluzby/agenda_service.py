"""Agregace úkolů a událostí pro společný pohled Agendy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from core.dashboard.attention_service import build_sort_key
from core.shared.task_source_display import task_source_short_label
from moduly.agenda.constants import (
    ITEM_TYPE_MEETING,
    ITEM_TYPE_TASK,
    SOURCE_LABEL_MEETING,
    STATUS_FILTER_MEETING_CANCELLED,
    STATUS_FILTER_MEETING_CLOSED,
    STATUS_FILTER_MEETING_HELD,
    STATUS_FILTER_MEETING_PLANNED,
    STATUS_FILTER_OVERDUE,
    STATUS_FILTER_TASK_CANCELLED,
    STATUS_FILTER_TASK_DONE,
    STATUS_FILTER_TASK_OPEN,
    TYPE_LABEL_MEETING,
    TYPE_LABEL_TASK,
)
from moduly.schuzky.constants import (
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_HELD,
    STATUS_PLANNED,
)
from moduly.schuzky.sluzby.meeting_service import meeting_service
from moduly.ukoly.sluzby.task_service import task_service


@dataclass(frozen=True)
class AgendaItem:
    item_type: str
    source_id: int
    type_label: str
    title: str
    person: str
    status: str
    source: str
    due_date: date | None = None
    event_at: datetime | None = None
    sort_key: tuple = ()
    status_tags: frozenset[str] = frozenset()

    @property
    def due_sort_datetime(self) -> datetime | None:
        if self.event_at is not None:
            return self.event_at
        if self.due_date is not None:
            return datetime.combine(self.due_date, time.min)
        return None


def _task_status_tags(task, *, today: date) -> frozenset[str]:
    tags: set[str] = set()
    status = task.computed_status or ""
    if status in ("Aktivní", "Splněno - čeká na kontrolu"):
        tags.add(STATUS_FILTER_TASK_OPEN)
    if status == "Ukončeno":
        tags.add(STATUS_FILTER_TASK_DONE)
    if status == "Zrušeno":
        tags.add(STATUS_FILTER_TASK_CANCELLED)
    if _is_task_overdue(task, today=today):
        tags.add(STATUS_FILTER_OVERDUE)
    return frozenset(tags)


def _meeting_status_tags(meeting, *, now: datetime) -> frozenset[str]:
    tags: set[str] = set()
    status = (meeting.status or "").strip()
    mapping = {
        STATUS_PLANNED: STATUS_FILTER_MEETING_PLANNED,
        STATUS_HELD: STATUS_FILTER_MEETING_HELD,
        STATUS_CLOSED: STATUS_FILTER_MEETING_CLOSED,
        STATUS_CANCELLED: STATUS_FILTER_MEETING_CANCELLED,
    }
    mapped = mapping.get(status)
    if mapped:
        tags.add(mapped)
    if _is_meeting_overdue(meeting, now=now):
        tags.add(STATUS_FILTER_OVERDUE)
    return frozenset(tags)


def _is_task_overdue(task, *, today: date) -> bool:
    if task.computed_status in ("Ukončeno", "Zrušeno"):
        return False
    due = task.due_date
    return due is not None and due < today


def _is_meeting_overdue(meeting, *, now: datetime) -> bool:
    if (meeting.status or "") != STATUS_PLANNED:
        return False
    starts = meeting.starts_at
    return starts is not None and starts < now


def _from_tasks(*, today: date) -> list[AgendaItem]:
    items: list[AgendaItem] = []
    for task in task_service.get_all_tasks():
        title = (task.title or "").strip() or "Bez názvu"
        status = task.computed_status or ""
        source = (task_source_short_label(task) or "").strip() or "—"
        person = (task.responsible_person or "").strip()
        items.append(
            AgendaItem(
                item_type=ITEM_TYPE_TASK,
                source_id=int(task.id),
                type_label=TYPE_LABEL_TASK,
                title=title,
                person=person,
                status=status,
                source=source,
                due_date=task.due_date,
                sort_key=build_sort_key(
                    task.due_date,
                    item_type=ITEM_TYPE_TASK,
                    title=title,
                    source_id=task.id,
                ),
                status_tags=_task_status_tags(task, today=today),
            )
        )
    return items


def _from_meetings(*, now: datetime) -> list[AgendaItem]:
    items: list[AgendaItem] = []
    for meeting in meeting_service.get_all():
        title = (meeting.title or "").strip() or "Bez názvu"
        event_type = (getattr(meeting, "event_type", None) or "").strip()
        if event_type:
            title = f"{event_type} – {title}"
        status = meeting.status or ""
        person = (meeting.organizer_name or "").strip()
        starts = meeting.starts_at
        items.append(
            AgendaItem(
                item_type=ITEM_TYPE_MEETING,
                source_id=int(meeting.id),
                type_label=TYPE_LABEL_MEETING,
                title=title,
                person=person,
                status=status,
                source=SOURCE_LABEL_MEETING,
                due_date=starts.date() if starts is not None else None,
                event_at=starts,
                sort_key=build_sort_key(
                    starts.date() if starts is not None else None,
                    item_type=ITEM_TYPE_MEETING,
                    title=title,
                    source_id=meeting.id,
                    due_datetime=starts,
                ),
                status_tags=_meeting_status_tags(meeting, now=now),
            )
        )
    return items


def get_agenda_items(
    *,
    today: date | None = None,
    now: datetime | None = None,
) -> list[AgendaItem]:
    """Vrátí chronologicky seřazený společný seznam úkolů a událostí."""
    now = now or datetime.now()
    today = today or now.date()
    items = _from_tasks(today=today) + _from_meetings(now=now)
    items.sort(key=lambda item: item.sort_key)
    return items


def filter_agenda_items(
    items: list[AgendaItem],
    *,
    type_filters: set[str],
    task_status_filters: set[str],
    meeting_status_filters: set[str],
) -> list[AgendaItem]:
    """
    Filtry Typ a Stav fungují společně (AND mezi skupinami, OR uvnitř skupiny).

    type_filters: ITEM_TYPE_TASK / ITEM_TYPE_MEETING
    *_status_filters: názvy z constants (Otevřený, Naplánováno, Po termínu, …)
    """
    if not type_filters:
        return []

    result: list[AgendaItem] = []
    for item in items:
        if item.item_type not in type_filters:
            continue
        if item.item_type == ITEM_TYPE_TASK:
            status_filters = task_status_filters
        else:
            status_filters = meeting_status_filters
        if not status_filters:
            continue
        if not (item.status_tags & status_filters):
            continue
        result.append(item)
    return result


agenda_service = type(
    "AgendaService",
    (),
    {
        "get_items": staticmethod(get_agenda_items),
        "filter_items": staticmethod(filter_agenda_items),
    },
)()
