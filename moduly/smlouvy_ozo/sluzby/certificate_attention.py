"""Upozornění na končící platnost osvědčení (OZO / ostatní)."""

from __future__ import annotations

from datetime import date

from moduly.smlouvy_ozo.constants import DEFAULT_NOTIFY_BEFORE_UNIT, UNIT_DAYS
from moduly.smlouvy_ozo.sluzby.ozo_contract_validity import notify_start_date


def is_certificate_due_for_attention(
    *,
    indefinite: bool,
    certificate_valid_to: date | None,
    notify_before_value: int = 0,
    notify_before_unit: str = UNIT_DAYS,
    today: date | None = None,
) -> bool:
    """True od předstihu (pokud je nastaven) nebo vždy po skončení platnosti.

    Bez předstihu (hodnota ≤ 0) se předem neupozorňuje; po platnosti ano.
    """
    if indefinite or certificate_valid_to is None:
        return False
    current = today or date.today()
    if current > certificate_valid_to:
        return True
    value = int(notify_before_value or 0)
    if value <= 0:
        return False
    notify_on = notify_start_date(
        certificate_valid_to,
        value,
        notify_before_unit or DEFAULT_NOTIFY_BEFORE_UNIT,
    )
    if notify_on is None:
        return False
    return current >= notify_on
