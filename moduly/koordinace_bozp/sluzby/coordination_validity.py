"""Výpočet a pomocné funkce platnosti koordinace (COORD-004)."""

from __future__ import annotations

from datetime import date, timedelta

from moduly.koordinace_bozp.constants import (
    VALIDITY_STATE_EXPIRED,
    VALIDITY_STATE_EXPIRING,
    VALIDITY_STATE_VALID,
    VALIDITY_STATE_COLORS,
    VALIDITY_STATES,
    VALIDITY_WARNING_DAYS,
)


def add_one_year(value: date) -> date:
    """Přidá jeden kalendářní rok (29. 2. → 28. 2. v nepřestupném roce)."""
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, month=2, day=28)


def resolve_validity_dates(
    meeting_date: date,
    *,
    valid_from: date | None = None,
    valid_to: date | None = None,
) -> tuple[date, date]:
    start = valid_from or meeting_date
    end = valid_to or add_one_year(start)
    return start, end


def coordination_validity_state(
    valid_to: date | None,
    *,
    today: date | None = None,
) -> str:
    """Vrátí valid / expiring / expired podle dynamických pravidel COORD-004."""
    if valid_to is None:
        return VALIDITY_STATE_EXPIRED
    current = today or date.today()
    warning_start = valid_to - timedelta(days=VALIDITY_WARNING_DAYS)
    if current > valid_to:
        return VALIDITY_STATE_EXPIRED
    if current <= warning_start:
        return VALIDITY_STATE_VALID
    return VALIDITY_STATE_EXPIRING


def coordination_validity_label(
    valid_to: date | None,
    *,
    today: date | None = None,
) -> str:
    state = coordination_validity_state(valid_to, today=today)
    if state == VALIDITY_STATE_EXPIRING and valid_to is not None:
        return f"Končí {valid_to.strftime('%d.%m.%Y')}"
    if state == VALIDITY_STATE_VALID:
        return "Platná"
    return "Po platnosti"


def coordination_validity_color(state: str) -> str:
    return VALIDITY_STATE_COLORS.get(state, VALIDITY_STATE_COLORS[VALIDITY_STATE_EXPIRED])


def coordination_validity_sort_order(state: str) -> int:
    try:
        return VALIDITY_STATES.index(state)
    except ValueError:
        return len(VALIDITY_STATES)
