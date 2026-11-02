"""Výjimky jednotlivých výskytů pevné kalendářní řady (RP-03).

Přesun a stav „Nevykoná se“ mění jen jeden výskyt. Počáteční rok, měsíc
a interval činnosti se tu nezapisují. Historie provedení se nečte ani nemění.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from moduly.periodicke_cinnosti.constants import (
    CALENDAR_MONTH_NAMES_FROM,
    CALENDAR_NOT_READY_MESSAGE,
    CALENDAR_SKIP_REASON_REQUIRED,
    CALENDAR_SLOT_NOT_ON_SERIES,
    CALENDAR_STATUS_TO_PLAN,
    CALENDAR_STATUS_WILL_NOT_PERFORM,
    MAX_CALENDAR_YEAR,
    MIN_CALENDAR_YEAR,
)
from moduly.periodicke_cinnosti.modely.periodic_activity import PeriodicActivity
from moduly.periodicke_cinnosti.modely.periodic_calendar_occurrence import (
    PeriodicCalendarOccurrence,
)
from moduly.periodicke_cinnosti.sluzby.periodic_calendar import (
    CalendarPeriodicityError,
    occurs_in_calendar_month,
)


class CalendarOccurrenceError(ValueError):
    """Výskyt nelze přesunout nebo označit."""


ALREADY_LINKED_MESSAGE = "Výskyt už má vazbu na úkol nebo událost."
SKIPPED_LINK_MESSAGE = (
    "Výskyt ve stavu Nevykoná se nelze navázat na úkol nebo událost."
)


@dataclass(frozen=True)
class CalendarOccurrenceView:
    original_year: int
    original_month: int
    display_year: int
    display_month: int
    status: str
    skip_reason: str
    task_id: int | None = None
    meeting_id: int | None = None


def calendar_is_ready(activity) -> bool:
    """True, pokud má činnost úplnou měsíční řadu a nečeká na ruční nastavení."""
    if activity is None or bool(getattr(activity, "calendar_setup_required", False)):
        return False
    return (
        getattr(activity, "calendar_start_year", None) is not None
        and getattr(activity, "calendar_start_month", None) is not None
        and getattr(activity, "calendar_interval_months", None) is not None
    )


def moved_from_label(year: int, month: int) -> str:
    if 1 <= int(month) <= 12:
        name = CALENDAR_MONTH_NAMES_FROM[int(month) - 1]
    else:
        name = str(month)
    return f"přesunuto z {name} {int(year)}"


def list_for_activity(activity_id: int) -> list[PeriodicCalendarOccurrence]:
    with get_session() as session:
        stmt = (
            select(PeriodicCalendarOccurrence)
            .where(PeriodicCalendarOccurrence.activity_id == activity_id)
            .order_by(
                PeriodicCalendarOccurrence.original_year,
                PeriodicCalendarOccurrence.original_month,
                PeriodicCalendarOccurrence.id,
            )
        )
        return list(session.scalars(stmt))


def views_for_display_month(
    activity,
    year: int,
    month: int,
    performed_months: set[tuple[int, int]],
) -> list[CalendarOccurrenceView]:
    """Výskyty zobrazené v měsíci. Provedený původní měsíc se znovu neotevírá."""
    if not calendar_is_ready(activity):
        return []

    exceptions = list_for_activity(activity.id)
    by_origin = {
        (item.original_year, item.original_month): item for item in exceptions
    }
    views: list[CalendarOccurrenceView] = []

    if _on_series(activity, year, month):
        current = by_origin.get((year, month))
        stays_here = current is None or (
            current.display_year == year and current.display_month == month
        )
        if stays_here and (year, month) not in performed_months:
            views.append(_view(year, month, current))

    for item in exceptions:
        if item.display_year != year or item.display_month != month:
            continue
        origin = (item.original_year, item.original_month)
        if origin == (year, month):
            continue
        if origin in performed_months:
            continue
        if not _on_series(activity, item.original_year, item.original_month):
            continue
        views.append(_view(item.original_year, item.original_month, item))
    return views


def move_occurrence(
    activity_id: int,
    *,
    original_year: int,
    original_month: int,
    to_year: int,
    to_month: int,
) -> PeriodicCalendarOccurrence | None:
    """Přesune jeden výskyt. Návrat do původního měsíce čistou výjimku smaže."""
    activity = _require_activity(activity_id)
    _require_slot(activity, original_year, original_month)
    _validate_target(to_year, to_month)
    with get_session() as session:
        row = _locked_slot(session, activity_id, original_year, original_month)
        if row is None:
            if (to_year, to_month) == (original_year, original_month):
                return None
            row = PeriodicCalendarOccurrence(
                activity_id=activity_id,
                original_year=original_year,
                original_month=original_month,
                display_year=to_year,
                display_month=to_month,
                status=CALENDAR_STATUS_TO_PLAN,
                skip_reason="",
            )
            session.add(row)
        else:
            row.display_year = to_year
            row.display_month = to_month
            row.updated_at = datetime.now()
            if _is_plain(row):
                session.delete(row)
                session.commit()
                return None
        session.commit()
        session.refresh(row)
        return row


def skip_occurrence(
    activity_id: int,
    *,
    original_year: int,
    original_month: int,
    reason: str,
) -> PeriodicCalendarOccurrence:
    """Označí výskyt jako Nevykoná se. Bez textu odůvodnění se nic neuloží."""
    text = (reason or "").strip()
    if not text:
        raise CalendarOccurrenceError(CALENDAR_SKIP_REASON_REQUIRED)
    activity = _require_activity(activity_id)
    _require_slot(activity, original_year, original_month)
    with get_session() as session:
        row = _locked_slot(session, activity_id, original_year, original_month)
        if row is None:
            row = PeriodicCalendarOccurrence(
                activity_id=activity_id,
                original_year=original_year,
                original_month=original_month,
                display_year=original_year,
                display_month=original_month,
                status=CALENDAR_STATUS_WILL_NOT_PERFORM,
                skip_reason=text,
            )
            session.add(row)
        else:
            row.status = CALENDAR_STATUS_WILL_NOT_PERFORM
            row.skip_reason = text
            row.updated_at = datetime.now()
        session.commit()
        session.refresh(row)
        return row


def get_occurrence(
    activity_id: int,
    original_year: int,
    original_month: int,
) -> PeriodicCalendarOccurrence | None:
    with get_session() as session:
        return _locked_slot(session, activity_id, original_year, original_month)


def link_task(
    activity_id: int,
    *,
    original_year: int,
    original_month: int,
    task_id: int,
) -> PeriodicCalendarOccurrence:
    """Zapíše vazbu na už uložený úkol. Přesun ani termín úkolu nemění."""
    return _link(
        activity_id,
        original_year=original_year,
        original_month=original_month,
        task_id=int(task_id),
        meeting_id=None,
    )


def link_meeting(
    activity_id: int,
    *,
    original_year: int,
    original_month: int,
    meeting_id: int,
) -> PeriodicCalendarOccurrence:
    """Zapíše vazbu na už uloženou událost. Přesun ani termín události nemění."""
    return _link(
        activity_id,
        original_year=original_year,
        original_month=original_month,
        task_id=None,
        meeting_id=int(meeting_id),
    )


def _link(
    activity_id: int,
    *,
    original_year: int,
    original_month: int,
    task_id: int | None,
    meeting_id: int | None,
) -> PeriodicCalendarOccurrence:
    if task_id is None and meeting_id is None:
        raise CalendarOccurrenceError("Chybí uložený úkol nebo událost.")
    if task_id is not None and meeting_id is not None:
        raise CalendarOccurrenceError(ALREADY_LINKED_MESSAGE)
    activity = _require_activity(activity_id)
    _require_slot(activity, original_year, original_month)
    with get_session() as session:
        row = _locked_slot(session, activity_id, original_year, original_month)
        if row is not None and (row.status or "") == CALENDAR_STATUS_WILL_NOT_PERFORM:
            raise CalendarOccurrenceError(SKIPPED_LINK_MESSAGE)
        if row is not None and (row.task_id is not None or row.meeting_id is not None):
            raise CalendarOccurrenceError(ALREADY_LINKED_MESSAGE)
        if row is None:
            row = PeriodicCalendarOccurrence(
                activity_id=activity_id,
                original_year=original_year,
                original_month=original_month,
                display_year=original_year,
                display_month=original_month,
                status=CALENDAR_STATUS_TO_PLAN,
                skip_reason="",
                task_id=task_id,
                meeting_id=meeting_id,
            )
            session.add(row)
        else:
            row.task_id = task_id
            row.meeting_id = meeting_id
            row.updated_at = datetime.now()
        session.commit()
        session.refresh(row)
        return row


def restore_to_planning(
    activity_id: int,
    *,
    original_year: int,
    original_month: int,
) -> PeriodicCalendarOccurrence | None:
    """Zruší Nevykoná se. Přesun do jiného měsíce ponechá."""
    activity = _require_activity(activity_id)
    _require_slot(activity, original_year, original_month)
    with get_session() as session:
        row = _locked_slot(session, activity_id, original_year, original_month)
        if row is None:
            return None
        row.status = CALENDAR_STATUS_TO_PLAN
        row.skip_reason = ""
        row.updated_at = datetime.now()
        if _is_plain(row):
            session.delete(row)
            session.commit()
            return None
        session.commit()
        session.refresh(row)
        return row


def _view(
    original_year: int,
    original_month: int,
    item: PeriodicCalendarOccurrence | None,
) -> CalendarOccurrenceView:
    if item is None:
        return CalendarOccurrenceView(
            original_year=original_year,
            original_month=original_month,
            display_year=original_year,
            display_month=original_month,
            status=CALENDAR_STATUS_TO_PLAN,
            skip_reason="",
        )
    status = item.status or CALENDAR_STATUS_TO_PLAN
    if status not in {CALENDAR_STATUS_TO_PLAN, CALENDAR_STATUS_WILL_NOT_PERFORM}:
        status = CALENDAR_STATUS_TO_PLAN
    return CalendarOccurrenceView(
        original_year=item.original_year,
        original_month=item.original_month,
        display_year=item.display_year,
        display_month=item.display_month,
        status=status,
        skip_reason=(item.skip_reason or "").strip(),
        task_id=item.task_id,
        meeting_id=item.meeting_id,
    )


def _require_activity(activity_id: int) -> PeriodicActivity:
    with get_session() as session:
        activity = session.get(PeriodicActivity, activity_id)
    if activity is None:
        raise CalendarOccurrenceError("Periodická činnost nebyla nalezena.")
    if not calendar_is_ready(activity):
        raise CalendarOccurrenceError(CALENDAR_NOT_READY_MESSAGE)
    return activity


def _require_slot(activity, year: int, month: int) -> None:
    if not _on_series(activity, year, month):
        raise CalendarOccurrenceError(CALENDAR_SLOT_NOT_ON_SERIES)


def _on_series(activity, year: int, month: int) -> bool:
    try:
        return occurs_in_calendar_month(
            start_year=int(activity.calendar_start_year),
            start_month=int(activity.calendar_start_month),
            interval_months=int(activity.calendar_interval_months),
            year=int(year),
            month=int(month),
        )
    except (CalendarPeriodicityError, TypeError, ValueError):
        return False


def _validate_target(year: int, month: int) -> None:
    if int(month) < 1 or int(month) > 12:
        raise CalendarOccurrenceError("Cílový měsíc musí být 1 až 12.")
    if int(year) < MIN_CALENDAR_YEAR or int(year) > MAX_CALENDAR_YEAR:
        raise CalendarOccurrenceError("Cílový rok je mimo povolený rozsah.")


def _locked_slot(
    session,
    activity_id: int,
    original_year: int,
    original_month: int,
) -> PeriodicCalendarOccurrence | None:
    stmt = select(PeriodicCalendarOccurrence).where(
        PeriodicCalendarOccurrence.activity_id == activity_id,
        PeriodicCalendarOccurrence.original_year == original_year,
        PeriodicCalendarOccurrence.original_month == original_month,
    )
    return session.scalars(stmt).first()


def _is_plain(row: PeriodicCalendarOccurrence) -> bool:
    return (
        (row.status or CALENDAR_STATUS_TO_PLAN) == CALENDAR_STATUS_TO_PLAN
        and not (row.skip_reason or "").strip()
        and row.task_id is None
        and row.meeting_id is None
        and row.display_year == row.original_year
        and row.display_month == row.original_month
    )
