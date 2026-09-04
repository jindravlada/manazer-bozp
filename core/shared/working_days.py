"""Společné výpočty pracovních dnů.

``is_working_day`` / ``first_working_day`` zůstávají Po–Pá bez svátků
(měsíční plánování). Státní a ostatní svátky podle zákona č. 245/2000 Sb.
řeší ``is_czech_public_holiday`` a ``add_czech_workdays``.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta


# Pevné státní a ostatní svátky (měsíc, den). 1. 1. je Nový rok i Den obnovy
# samostatného českého státu – v kalendáři jeden den.
_CZECH_FIXED_HOLIDAYS = (
    (1, 1),
    (5, 1),
    (5, 8),
    (7, 5),
    (7, 6),
    (9, 28),
    (10, 28),
    (11, 17),
    (12, 24),
    (12, 25),
    (12, 26),
)


def is_working_day(value: date) -> bool:
    """True, pokud den spadá na pondělí–pátek."""
    return value.weekday() < 5


def easter_sunday(year: int) -> date:
    """Neděle velikonoční v gregoriánském kalendáři (anonymní algoritmus)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def is_czech_public_holiday(value: date) -> bool:
    """True pro státní i ostatní svátky ČR, včetně Velkého pátku a Velikonočního pondělí."""
    if (value.month, value.day) in _CZECH_FIXED_HOLIDAYS:
        return True
    easter = easter_sunday(value.year)
    return value in {easter - timedelta(days=2), easter + timedelta(days=1)}


def is_czech_working_day(value: date) -> bool:
    """Pracovní den: pondělí–pátek mimo české státní a ostatní svátky."""
    return is_working_day(value) and not is_czech_public_holiday(value)


def add_czech_workdays(start_date: date, days: int) -> date:
    """
    Přičte ``days`` českých pracovních dnů ode dne následujícího po ``start_date``.

    Soboty, neděle a české svátky se nepočítají. Výsledkem je vždy pracovní den.
    """
    result = start_date
    added = 0
    while added < days:
        result = result + timedelta(days=1)
        if is_czech_working_day(result):
            added += 1
    return result


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
