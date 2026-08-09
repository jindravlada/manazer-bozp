"""Společné výpočty pracovních dnů (Po–Pá; svátky zatím neřešíme)."""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def is_working_day(value: date) -> bool:
    """True, pokud den spadá na pondělí–pátek."""
    return value.weekday() < 5


def first_working_day(year: int, month: int) -> date:
    """
    První pracovní den (Po–Pá) v daném kalendářním měsíci.

    Pokud měsíc začíná o víkendu, posune se na následující pondělí.
    """
    if month < 1 or month > 12:
        raise ValueError("Měsíc musí být v rozmezí 1–12.")
    day = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    while day.day <= last_day:
        if is_working_day(day):
            return day
        day += timedelta(days=1)
    raise ValueError(f"V měsíci {month}/{year} nebyl nalezen pracovní den.")
