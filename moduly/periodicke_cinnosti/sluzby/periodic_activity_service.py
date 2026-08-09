"""Služba Periodických činností – CRUD, validace, výpočet dalšího termínu."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from moduly.periodicke_cinnosti.constants import (
    DEFAULT_NEXT_FROM,
    DEFAULT_NOTIFY_EVERY,
    DEFAULT_NOTIFY_UNIT,
    DEFAULT_PLACE_KIND,
    DEFAULT_REPEAT_EVERY,
    DEFAULT_REPEAT_UNIT,
    NEXT_FROM_ACTUAL,
    NEXT_FROM_PLANNED,
    NEXT_FROM_VALUES,
    PLACE_KINDS,
    TIME_UNITS,
    UNIT_DAYS,
    UNIT_MONTHS,
    UNIT_WEEKS,
    UNIT_YEARS,
)
from moduly.periodicke_cinnosti.modely.periodic_activity import PeriodicActivity
from moduly.periodicke_cinnosti.modely.periodic_activity_occurrence import (
    PeriodicActivityOccurrence,
)
from moduly.periodicke_cinnosti.repository.periodic_activity_repository import (
    PeriodicActivityOccurrenceRepository,
    PeriodicActivityRepository,
)


class PeriodicActivityValidationError(ValueError):
    """Neplatná data periodické činnosti."""


def add_calendar_months(value: date, months: int) -> date:
    """Přičte měsíce kalendářně (den ořízne na konec cílového měsíce)."""
    year = value.year
    month = value.month + months
    while month > 12:
        year += 1
        month -= 12
    while month < 1:
        year -= 1
        month += 12
    last_day = calendar.monthrange(year, month)[1]
    day = min(value.day, last_day)
    return date(year, month, day)


def add_period(value: date, every: int, unit: str) -> date:
    """Přičte jednu periodu (every × unit) ke datu."""
    if every <= 0:
        raise PeriodicActivityValidationError("repeat_every musí být větší než 0.")
    if unit == UNIT_DAYS:
        return value + timedelta(days=every)
    if unit == UNIT_WEEKS:
        return value + timedelta(weeks=every)
    if unit == UNIT_MONTHS:
        return add_calendar_months(value, every)
    if unit == UNIT_YEARS:
        return add_calendar_months(value, every * 12)
    raise PeriodicActivityValidationError(f"Nepodporovaná jednotka periody: {unit}")


def calculate_next_due_date(
    *,
    planned_due_date: date | None,
    performed_at: date,
    repeat_every: int,
    repeat_unit: str,
    next_from: str,
) -> date:
    """
    Vypočítá další termín po provedení.

    next_from=actual: provedení + perioda.
    next_from=planned: vždy alespoň jedna perioda od plánu, pak další periody,
    dokud výsledek není ostře po skutečném provedení.
    """
    if next_from not in NEXT_FROM_VALUES:
        raise PeriodicActivityValidationError(
            f"next_from musí být jedna z: {', '.join(NEXT_FROM_VALUES)}."
        )
    if repeat_every <= 0:
        raise PeriodicActivityValidationError("repeat_every musí být větší než 0.")
    if repeat_unit not in TIME_UNITS:
        raise PeriodicActivityValidationError(
            f"repeat_unit musí být jedna z: {', '.join(TIME_UNITS)}."
        )

    if next_from == NEXT_FROM_ACTUAL:
        return add_period(performed_at, repeat_every, repeat_unit)

    if planned_due_date is None:
        raise PeriodicActivityValidationError(
            "Pro next_from=planned je vyžadován plánovaný termín."
        )

    candidate = planned_due_date
    while True:
        candidate = add_period(candidate, repeat_every, repeat_unit)
        if candidate > performed_at:
            return candidate


class PeriodicActivityService:
    def __init__(self) -> None:
        self.repository = PeriodicActivityRepository()
        self.occurrence_repository = PeriodicActivityOccurrenceRepository()

    def get_all(self, *, active_only: bool | None = None) -> list[PeriodicActivity]:
        return self.repository.get_all(active_only=active_only)

    def get_by_id(self, activity_id: int) -> PeriodicActivity | None:
        return self.repository.get_by_id(activity_id)

    def list_occurrences(self, activity_id: int) -> list[PeriodicActivityOccurrence]:
        return self.occurrence_repository.list_for_activity(activity_id)

    def create_activity(
        self,
        *,
        title: str,
        place_kind: str = DEFAULT_PLACE_KIND,
        workplace_id: int | None = None,
        workplace_name: str = "",
        place_text: str = "",
        responsible_person_id: int | None = None,
        responsible_person_name: str = "",
        next_due_date: date | None = None,
        repeat_every: int = DEFAULT_REPEAT_EVERY,
        repeat_unit: str = DEFAULT_REPEAT_UNIT,
        notify_every: int = DEFAULT_NOTIFY_EVERY,
        notify_unit: str = DEFAULT_NOTIFY_UNIT,
        next_from: str = DEFAULT_NEXT_FROM,
        note: str = "",
        active: bool = True,
    ) -> PeriodicActivity:
        data = self._validated_fields(
            title=title,
            place_kind=place_kind,
            workplace_id=workplace_id,
            workplace_name=workplace_name,
            place_text=place_text,
            responsible_person_id=responsible_person_id,
            responsible_person_name=responsible_person_name,
            next_due_date=next_due_date,
            repeat_every=repeat_every,
            repeat_unit=repeat_unit,
            notify_every=notify_every,
            notify_unit=notify_unit,
            next_from=next_from,
            note=note,
            active=active,
        )
        activity = PeriodicActivity(**data)
        return self.repository.add(activity)

    def update_activity(
        self,
        activity_id: int,
        *,
        title: str,
        place_kind: str = DEFAULT_PLACE_KIND,
        workplace_id: int | None = None,
        workplace_name: str = "",
        place_text: str = "",
        responsible_person_id: int | None = None,
        responsible_person_name: str = "",
        next_due_date: date | None = None,
        repeat_every: int = DEFAULT_REPEAT_EVERY,
        repeat_unit: str = DEFAULT_REPEAT_UNIT,
        notify_every: int = DEFAULT_NOTIFY_EVERY,
        notify_unit: str = DEFAULT_NOTIFY_UNIT,
        next_from: str = DEFAULT_NEXT_FROM,
        note: str = "",
        active: bool = True,
    ) -> PeriodicActivity:
        activity = self.repository.get_by_id(activity_id)
        if activity is None:
            raise PeriodicActivityValidationError("Periodická činnost nebyla nalezena.")

        data = self._validated_fields(
            title=title,
            place_kind=place_kind,
            workplace_id=workplace_id,
            workplace_name=workplace_name,
            place_text=place_text,
            responsible_person_id=responsible_person_id,
            responsible_person_name=responsible_person_name,
            next_due_date=next_due_date,
            repeat_every=repeat_every,
            repeat_unit=repeat_unit,
            notify_every=notify_every,
            notify_unit=notify_unit,
            next_from=next_from,
            note=note,
            active=active,
        )
        for key, value in data.items():
            setattr(activity, key, value)
        activity.updated_at = datetime.now()
        return self.repository.update(activity)

    def record_performance(
        self,
        activity_id: int,
        *,
        performed_at: date,
        performed_by_id: int | None = None,
        performed_by_name: str = "",
        result_note: str = "",
    ) -> PeriodicActivityOccurrence:
        """
        Vytvoří historický záznam a přepočítá next_due_date.
        Existující occurrence řádky se nemění.
        """
        activity = self.repository.get_by_id(activity_id)
        if activity is None:
            raise PeriodicActivityValidationError("Periodická činnost nebyla nalezena.")

        planned = activity.next_due_date
        next_due = calculate_next_due_date(
            planned_due_date=planned,
            performed_at=performed_at,
            repeat_every=activity.repeat_every,
            repeat_unit=activity.repeat_unit,
            next_from=activity.next_from,
        )

        occurrence = PeriodicActivityOccurrence(
            activity_id=activity.id,
            planned_due_date=planned,
            performed_at=performed_at,
            performed_by_id=performed_by_id,
            performed_by_name=(performed_by_name or "").strip(),
            result_note=(result_note or "").strip(),
        )
        saved = self.occurrence_repository.add(occurrence)

        activity.next_due_date = next_due
        activity.updated_at = datetime.now()
        self.repository.update(activity)
        return saved

    def _validated_fields(
        self,
        *,
        title: str,
        place_kind: str,
        workplace_id: int | None,
        workplace_name: str,
        place_text: str,
        responsible_person_id: int | None,
        responsible_person_name: str,
        next_due_date: date | None,
        repeat_every: int,
        repeat_unit: str,
        notify_every: int,
        notify_unit: str,
        next_from: str,
        note: str,
        active: bool,
    ) -> dict:
        clean_title = (title or "").strip()
        if not clean_title:
            raise PeriodicActivityValidationError("Název nesmí být prázdný.")

        if place_kind not in PLACE_KINDS:
            raise PeriodicActivityValidationError(
                f"place_kind musí být jedna z: {', '.join(PLACE_KINDS)}."
            )
        if repeat_every <= 0:
            raise PeriodicActivityValidationError("repeat_every musí být větší než 0.")
        if notify_every < 0:
            raise PeriodicActivityValidationError("notify_every nesmí být záporné.")
        if repeat_unit not in TIME_UNITS:
            raise PeriodicActivityValidationError(
                f"repeat_unit musí být jedna z: {', '.join(TIME_UNITS)}."
            )
        if notify_unit not in TIME_UNITS:
            raise PeriodicActivityValidationError(
                f"notify_unit musí být jedna z: {', '.join(TIME_UNITS)}."
            )
        if next_from not in NEXT_FROM_VALUES:
            raise PeriodicActivityValidationError(
                f"next_from musí být jedna z: {', '.join(NEXT_FROM_VALUES)}."
            )

        return {
            "title": clean_title,
            "place_kind": place_kind,
            "workplace_id": workplace_id,
            "workplace_name": (workplace_name or "").strip(),
            "place_text": (place_text or "").strip(),
            "responsible_person_id": responsible_person_id,
            "responsible_person_name": (responsible_person_name or "").strip(),
            "next_due_date": next_due_date,
            "repeat_every": int(repeat_every),
            "repeat_unit": repeat_unit,
            "notify_every": int(notify_every),
            "notify_unit": notify_unit,
            "next_from": next_from,
            "note": (note or "").strip(),
            "active": bool(active),
        }


periodic_activity_service = PeriodicActivityService()
