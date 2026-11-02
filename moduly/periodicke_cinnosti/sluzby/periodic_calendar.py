"""Pevná kalendářní periodicita (RP-02).

Řada měsíců se počítá jen z počátečního roku, měsíce a intervalu.
Datum provedení, historie, úkol, událost ani přesun výskytu do ní nevstupují.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from moduly.periodicke_cinnosti.constants import (
    MAX_CALENDAR_YEAR,
    MIN_CALENDAR_YEAR,
    UNIT_DAYS,
    UNIT_MONTHS,
    UNIT_WEEKS,
    UNIT_YEARS,
)
from moduly.periodicke_cinnosti.modely.periodic_activity import PeriodicActivity


class CalendarPeriodicityError(ValueError):
    """Neplatný počátek nebo interval kalendářní řady."""


def list_calendar_occurrences(
    *,
    start_year: int,
    start_month: int,
    interval_months: int,
    until_year: int,
    until_month: int,
) -> list[tuple[int, int]]:
    """Měsíce od kotvy po `until` včetně, po kroku `interval_months`.

    Vrací dvojice (rok, měsíc). Měsíc před kotvou v seznamu není.
    """
    _validate_anchor(start_year, start_month, interval_months)
    _validate_month(until_month)
    if until_year < MIN_CALENDAR_YEAR or until_year > MAX_CALENDAR_YEAR:
        raise CalendarPeriodicityError("Rok konce řady je mimo povolený rozsah.")

    start = _month_index(start_year, start_month)
    until = _month_index(until_year, until_month)
    if until < start:
        return []

    found: list[tuple[int, int]] = []
    index = start
    while index <= until:
        found.append(_index_to_month(index))
        index += interval_months
    return found


def occurs_in_calendar_month(
    *,
    start_year: int,
    start_month: int,
    interval_months: int,
    year: int,
    month: int,
) -> bool:
    """True, pokud měsíc leží na pevné řadě od kotvy."""
    _validate_anchor(start_year, start_month, interval_months)
    _validate_month(month)
    start = _month_index(start_year, start_month)
    target = _month_index(year, month)
    if target < start:
        return False
    return (target - start) % interval_months == 0


def plan_calendar_migration(activity) -> dict | None:
    """Co doplnit do jedné existující činnosti. None = řádek už se nesmí měnit.

    Měsíce a roky se odvodí z `next_due_date`. Dny a týdny se nepřevádějí,
    jen se označí k ručnímu nastavení. `next_due_date`, `repeat_*` a `next_from`
    tahle funkce nevrací, takže je volající nesmí přepsat.
    """
    if getattr(activity, "calendar_start_year", None) is not None:
        return None
    if bool(getattr(activity, "calendar_setup_required", False)):
        return None

    unit = (getattr(activity, "repeat_unit", "") or "").strip()
    if unit in {UNIT_DAYS, UNIT_WEEKS}:
        return {"calendar_setup_required": True}

    if unit in {UNIT_MONTHS, UNIT_YEARS}:
        due = getattr(activity, "next_due_date", None)
        every = int(getattr(activity, "repeat_every", 0) or 0)
        if due is None or every <= 0:
            return {"calendar_setup_required": True}
        months = every if unit == UNIT_MONTHS else every * 12
        return {
            "calendar_start_year": int(due.year),
            "calendar_start_month": int(due.month),
            "calendar_interval_months": int(months),
            "calendar_setup_required": False,
        }

    return {"calendar_setup_required": True}


def apply_calendar_periodicity_migration() -> int:
    """Doplní kalendářní pole. Opakované volání už převedené řádky nemění."""
    changed = 0
    with get_session() as session:
        rows = list(session.scalars(select(PeriodicActivity).order_by(PeriodicActivity.id)))
        for activity in rows:
            decision = plan_calendar_migration(activity)
            if decision is None:
                continue
            for key, value in decision.items():
                setattr(activity, key, value)
            activity.updated_at = datetime.now()
            changed += 1
        if changed:
            session.commit()
    return changed


def _month_index(year: int, month: int) -> int:
    return int(year) * 12 + (int(month) - 1)


def _index_to_month(index: int) -> tuple[int, int]:
    year, month_zero = divmod(index, 12)
    return year, month_zero + 1


def _validate_month(month: int) -> None:
    if int(month) < 1 or int(month) > 12:
        raise CalendarPeriodicityError("Měsíc musí být 1 až 12.")


def _validate_anchor(start_year: int, start_month: int, interval_months: int) -> None:
    if int(start_year) < MIN_CALENDAR_YEAR or int(start_year) > MAX_CALENDAR_YEAR:
        raise CalendarPeriodicityError("Počáteční rok je mimo povolený rozsah.")
    _validate_month(start_month)
    if int(interval_months) < 1:
        raise CalendarPeriodicityError("Interval v měsících musí být alespoň 1.")
