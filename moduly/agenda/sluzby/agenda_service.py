"""Agregace úkolů a událostí pro společný pohled Agendy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from core.shared.task_source_display import task_source_short_label
from moduly.agenda.constants import (
    DEFAULT_PRIORITY,
    ITEM_TYPE_MEETING,
    ITEM_TYPE_TASK,
    ROW_STATE_ACTIVE,
    ROW_STATE_CANCELED,
    ROW_STATE_DONE,
    ROW_STATE_OVERDUE,
    ROW_STATE_WAITING,
    SOURCE_LABEL_MEETING,
    STATUS_MODE_ACTIVE,
    STATUS_MODE_ALL,
    STATUS_MODE_CANCELLED,
    STATUS_MODE_CLOSED,
    STATUS_MODE_DONE,
    STATUS_MODE_PLANNED,
    TYPE_LABEL_MEETING,
    TYPE_LABEL_TASK,
)
from moduly.schuzky.constants import (
    DEFAULT_MEETING_PRIORITY,
    MEETING_PRIORITIES,
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_PLANNED,
)
from moduly.schuzky.sluzby.meeting_service import meeting_service
from moduly.ukoly.sluzby.task_service import task_service


def _build_sort_key(*args, **kwargs):
    # Lazy import – přeruší cyklus agenda_service ↔ core.dashboard.
    from core.dashboard.attention_service import build_sort_key

    return build_sort_key(*args, **kwargs)


@dataclass(frozen=True)
class AgendaItem:
    item_type: str
    source_id: int
    type_label: str
    title: str
    person: str
    status: str
    source: str
    row_state: str = ROW_STATE_ACTIVE
    priority: str = DEFAULT_PRIORITY
    due_date: date | None = None
    event_at: datetime | None = None
    ends_at: datetime | None = None
    base_title: str = ""
    sort_key: tuple = ()

    @property
    def due_sort_datetime(self) -> datetime | None:
        if self.event_at is not None:
            return self.event_at
        if self.due_date is not None:
            return datetime.combine(self.due_date, time.min)
        return None

    @property
    def tooltip_title(self) -> str:
        return (self.base_title or self.title or "").strip() or "Bez názvu"


def _normalize_priority(value: str | None) -> str:
    text = (value or "").strip()
    if text in MEETING_PRIORITIES:
        return text
    return DEFAULT_PRIORITY


def _task_row_state(task, *, today: date) -> str:
    """Stejná logika jako TaskTable._row_state."""
    status = task.computed_status
    if status == "Zrušeno":
        return ROW_STATE_CANCELED
    if status == "Ukončeno":
        return ROW_STATE_DONE
    if task.due_date is not None and task.due_date < today:
        return ROW_STATE_OVERDUE
    if status == "Splněno - čeká na kontrolu":
        return ROW_STATE_WAITING
    return ROW_STATE_ACTIVE


def _meeting_row_state(meeting, *, now: datetime) -> str:
    status = meeting_service.normalize_status(meeting.status)
    if status == STATUS_CANCELLED:
        return ROW_STATE_CANCELED
    if status == STATUS_CLOSED:
        return ROW_STATE_DONE
    if status == STATUS_PLANNED:
        starts = meeting.starts_at
        if starts is not None and starts < now:
            return ROW_STATE_OVERDUE
        return ROW_STATE_ACTIVE
    return ROW_STATE_ACTIVE


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
                row_state=_task_row_state(task, today=today),
                priority=_normalize_priority(getattr(task, "priority", None)),
                due_date=task.due_date,
                base_title=title,
                sort_key=_build_sort_key(
                    task.due_date,
                    item_type=ITEM_TYPE_TASK,
                    title=title,
                    source_id=task.id,
                ),
            )
        )
    return items


def _from_meetings(*, now: datetime) -> list[AgendaItem]:
    items: list[AgendaItem] = []
    for meeting in meeting_service.get_all():
        title = (meeting.title or "").strip() or "Bez názvu"
        base_title = title
        event_type = (getattr(meeting, "event_type", None) or "").strip()
        if event_type:
            title = f"{event_type} – {title}"
        status = meeting_service.normalize_status(meeting.status)
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
                row_state=_meeting_row_state(meeting, now=now),
                priority=_normalize_priority(
                    getattr(meeting, "priority", None) or DEFAULT_MEETING_PRIORITY
                ),
                due_date=starts.date() if starts is not None else None,
                event_at=starts,
                ends_at=meeting.ends_at,
                base_title=base_title,
                sort_key=_build_sort_key(
                    starts.date() if starts is not None else None,
                    item_type=ITEM_TYPE_MEETING,
                    title=title,
                    source_id=meeting.id,
                    due_datetime=starts,
                ),
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


def _task_matches_status_mode(item: AgendaItem, mode: str) -> bool:
    status = item.status or ""
    if mode == STATUS_MODE_ALL:
        return True
    if mode == STATUS_MODE_ACTIVE:
        return status not in ("Ukončeno", "Zrušeno")
    if mode == STATUS_MODE_DONE:
        return status == "Ukončeno"
    if mode == STATUS_MODE_CANCELLED:
        return status == "Zrušeno"
    return False


def _meeting_matches_status_mode(item: AgendaItem, mode: str) -> bool:
    status = meeting_service.normalize_status(item.status)
    if mode == STATUS_MODE_ALL:
        return True
    if mode == STATUS_MODE_ACTIVE:
        # Aktivní = naplánované (včetně po termínu).
        return status == STATUS_PLANNED
    if mode == STATUS_MODE_PLANNED:
        return status == STATUS_PLANNED
    if mode == STATUS_MODE_CLOSED:
        return status == STATUS_CLOSED
    if mode == STATUS_MODE_CANCELLED:
        return status == STATUS_CANCELLED
    if mode == STATUS_MODE_DONE:
        # Splněné v kombinovaném pohledu = uzavřené události.
        return status == STATUS_CLOSED
    return False


def filter_agenda_items(
    items: list[AgendaItem],
    *,
    type_filters: set[str],
    status_mode: str,
) -> list[AgendaItem]:
    """Filtr Typ (checkboxy) + společný režim stavu (combobox)."""
    if not type_filters:
        return []

    result: list[AgendaItem] = []
    for item in items:
        if item.item_type not in type_filters:
            continue
        if item.item_type == ITEM_TYPE_TASK:
            if not _task_matches_status_mode(item, status_mode):
                continue
        else:
            if not _meeting_matches_status_mode(item, status_mode):
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
