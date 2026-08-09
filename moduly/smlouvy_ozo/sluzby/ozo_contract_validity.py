"""Odvození stavu platnosti smlouvy OZO."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from moduly.smlouvy_ozo.constants import (
    DEFAULT_NOTIFY_BEFORE_UNIT,
    STATUS_ACTIVE,
    STATUS_ENDING,
    STATUS_EXPIRED,
    STATUS_INACTIVE,
    UNIT_DAYS,
    UNIT_MONTHS,
    UNIT_WEEKS,
    NOTIFY_UNITS,
)


def _add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def subtract_notify_period(value: date, every: int, unit: str) -> date:
    """Odečte předstih (every × unit) od data konce platnosti."""
    every = int(every or 0)
    unit = unit or DEFAULT_NOTIFY_BEFORE_UNIT
    if every <= 0:
        return value
    if unit == UNIT_DAYS:
        return value - timedelta(days=every)
    if unit == UNIT_WEEKS:
        return value - timedelta(weeks=every)
    if unit == UNIT_MONTHS:
        return _add_calendar_months(value, -every)
    return value


def notify_start_date(
    valid_to: date | None,
    notify_before_value: int,
    notify_before_unit: str,
) -> date | None:
    if valid_to is None:
        return None
    unit = notify_before_unit if notify_before_unit in NOTIFY_UNITS else DEFAULT_NOTIFY_BEFORE_UNIT
    return subtract_notify_period(valid_to, notify_before_value, unit)


def contract_status(
    *,
    active: bool,
    indefinite: bool,
    valid_to: date | None,
    notify_before_value: int = 0,
    notify_before_unit: str = DEFAULT_NOTIFY_BEFORE_UNIT,
    today: date | None = None,
) -> str:
    """Vrátí inactive / active / ending / expired (neukládá se do DB)."""
    if not active:
        return STATUS_INACTIVE
    if indefinite or valid_to is None:
        return STATUS_ACTIVE
    current = today or date.today()
    if current > valid_to:
        return STATUS_EXPIRED
    start = notify_start_date(valid_to, notify_before_value, notify_before_unit)
    if start is not None and current >= start:
        return STATUS_ENDING
    return STATUS_ACTIVE


def is_due_for_attention(
    *,
    active: bool,
    indefinite: bool,
    valid_to: date | None,
    notify_before_value: int = 0,
    notify_before_unit: str = DEFAULT_NOTIFY_BEFORE_UNIT,
    today: date | None = None,
) -> bool:
    """True od data upozornění (valid_to − předstih) u aktivní smlouvy na dobu určitou."""
    if not active or indefinite or valid_to is None:
        return False
    notify_on = notify_start_date(
        valid_to,
        notify_before_value,
        notify_before_unit,
    )
    if notify_on is None:
        return False
    current = today or date.today()
    return current >= notify_on
