"""Rozsah náhrady pracovního úrazu po ukončení DPN – JSON šetření, bez částek odškodnění."""

from __future__ import annotations

from typing import Any

from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    AccidentLike,
    is_dpn_ended,
)


DPN_EMPLOYER_RESPONSIBILITY_KEY = "dpn_employer_responsibility"

RESP_PROPOSED_PERCENT = "proposed_percent"
RESP_RECOGNIZED_PERCENT = "recognized_percent"
RESP_NOTE = "note"

PERCENT_MIN = 0
PERCENT_MAX = 100


def empty_dpn_employer_responsibility() -> dict[str, Any]:
    return {
        RESP_PROPOSED_PERCENT: None,
        RESP_RECOGNIZED_PERCENT: None,
        RESP_NOTE: "",
    }


def normalize_percent(value: Any) -> int | None:
    """Vrátí celé číslo 0–100, jinak None. Prázdné zůstane prázdné, 0 je platná hodnota."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip().replace("%", "").replace(",", ".").strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    else:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
    percent = int(round(number))
    if percent < PERCENT_MIN or percent > PERCENT_MAX:
        return None
    return percent


def reduction_percent(value: Any) -> int | None:
    """Krácení náhrady: 100 − rozsah. Prázdný rozsah nemá krácení."""
    percent = normalize_percent(value)
    if percent is None:
        return None
    return PERCENT_MAX - percent


def normalize_dpn_employer_responsibility(state: dict[str, Any] | None) -> dict[str, Any]:
    data = state if isinstance(state, dict) else {}
    return {
        RESP_PROPOSED_PERCENT: normalize_percent(data.get(RESP_PROPOSED_PERCENT)),
        RESP_RECOGNIZED_PERCENT: normalize_percent(data.get(RESP_RECOGNIZED_PERCENT)),
        RESP_NOTE: str(data.get(RESP_NOTE) or "").strip(),
    }


def dpn_employer_responsibility_from_saved_data(
    saved_data: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(saved_data, dict):
        return empty_dpn_employer_responsibility()
    raw = saved_data.get(DPN_EMPLOYER_RESPONSIBILITY_KEY)
    if not isinstance(raw, dict):
        return empty_dpn_employer_responsibility()
    return normalize_dpn_employer_responsibility(raw)


def dpn_employer_responsibility_has_progress(state: dict[str, Any] | None) -> bool:
    data = normalize_dpn_employer_responsibility(state)
    return (
        data[RESP_PROPOSED_PERCENT] is not None
        or data[RESP_RECOGNIZED_PERCENT] is not None
        or bool(data[RESP_NOTE])
    )


def apply_dpn_employer_responsibility_to_saved_data(
    saved_data: dict[str, Any] | None,
    *,
    accident: AccidentLike | None,
    ui_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Zapíše rozsah náhrady. Návrh a skutečnost se navzájem nekopírují."""
    data = dict(saved_data or {})
    existing = dpn_employer_responsibility_from_saved_data(data)
    if ui_state is None:
        return data

    normalized = normalize_dpn_employer_responsibility(ui_state)
    if dpn_employer_responsibility_has_progress(normalized):
        data[DPN_EMPLOYER_RESPONSIBILITY_KEY] = normalized
        return data

    dpn_ended = is_dpn_ended(
        getattr(accident, "dpn_do", None) if accident is not None else None
    )
    if not dpn_ended and dpn_employer_responsibility_has_progress(existing):
        return data

    data.pop(DPN_EMPLOYER_RESPONSIBILITY_KEY, None)
    return data
