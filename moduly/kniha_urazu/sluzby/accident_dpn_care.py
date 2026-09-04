"""Péče a návrat do práce po ukončení DPN – JSON šetření, bez zdravotních diagnóz."""

from __future__ import annotations

from typing import Any

from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    AccidentLike,
    is_dpn_ended,
    parse_saved_date,
)


DPN_CARE_RETURN_KEY = "dpn_care_return"

CARE_EXAM_REQUIRED = "exam_required"
CARE_EXAM_REASON = "exam_reason"
CARE_EXAM_DATE = "exam_date"
CARE_EXAM_RESULT = "exam_result"
CARE_RETURN_DATE = "return_date"
CARE_RETURN_MODE = "return_mode"

EXAM_REQUIRED_YES = "ANO"
EXAM_REQUIRED_NO = "NE"

EXAM_RESULT_FIT = "zdravotně způsobilý"
EXAM_RESULT_FIT_CONDITIONAL = "zdravotně způsobilý s podmínkou"
EXAM_RESULT_LONG_TERM_UNFIT = "dlouhodobě pozbyl zdravotní způsobilost"
EXAM_RESULT_OTHER = "jiný výsledek"

EXAM_RESULTS = (
    EXAM_RESULT_FIT,
    EXAM_RESULT_FIT_CONDITIONAL,
    EXAM_RESULT_LONG_TERM_UNFIT,
    EXAM_RESULT_OTHER,
)

RETURN_MODE_SAME = "návrat na dosavadní práci"
RETURN_MODE_SAME_CONDITIONAL = "návrat na dosavadní práci s omezením/podmínkou"
RETURN_MODE_TRANSFER = "převedení na jinou práci"
RETURN_MODE_ENDED = "pracovní poměr ukončen"
RETURN_MODE_NOT_STARTED = "dosud nenastoupil"
RETURN_MODE_OTHER = "jiné"

RETURN_MODES = (
    RETURN_MODE_SAME,
    RETURN_MODE_SAME_CONDITIONAL,
    RETURN_MODE_TRANSFER,
    RETURN_MODE_ENDED,
    RETURN_MODE_NOT_STARTED,
    RETURN_MODE_OTHER,
)


def empty_dpn_care_return() -> dict[str, Any]:
    return {
        CARE_EXAM_REQUIRED: "",
        CARE_EXAM_REASON: "",
        CARE_EXAM_DATE: None,
        CARE_EXAM_RESULT: "",
        CARE_RETURN_DATE: None,
        CARE_RETURN_MODE: "",
    }


def _date_json(value: Any) -> str | None:
    parsed = parse_saved_date(value)
    return parsed.isoformat() if parsed else None


def _normalize_exam_required(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {EXAM_REQUIRED_YES, "A", "YES", "TRUE", "1"}:
        return EXAM_REQUIRED_YES
    if text in {EXAM_REQUIRED_NO, "N", "NO", "FALSE", "0"}:
        return EXAM_REQUIRED_NO
    return ""


def _normalize_choice(value: Any, allowed: tuple[str, ...]) -> str:
    text = str(value or "").strip()
    if text in allowed:
        return text
    lowered = text.lower()
    for item in allowed:
        if item.lower() == lowered:
            return item
    return ""


def normalize_dpn_care_return(state: dict[str, Any] | None) -> dict[str, Any]:
    data = state if isinstance(state, dict) else {}
    return {
        CARE_EXAM_REQUIRED: _normalize_exam_required(data.get(CARE_EXAM_REQUIRED)),
        CARE_EXAM_REASON: str(data.get(CARE_EXAM_REASON) or "").strip(),
        CARE_EXAM_DATE: _date_json(data.get(CARE_EXAM_DATE)),
        CARE_EXAM_RESULT: _normalize_choice(data.get(CARE_EXAM_RESULT), EXAM_RESULTS),
        CARE_RETURN_DATE: _date_json(data.get(CARE_RETURN_DATE)),
        CARE_RETURN_MODE: _normalize_choice(data.get(CARE_RETURN_MODE), RETURN_MODES),
    }


def dpn_care_return_from_saved_data(saved_data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(saved_data, dict):
        return empty_dpn_care_return()
    raw = saved_data.get(DPN_CARE_RETURN_KEY)
    if not isinstance(raw, dict):
        return empty_dpn_care_return()
    return normalize_dpn_care_return(raw)


def dpn_care_return_has_progress(state: dict[str, Any] | None) -> bool:
    data = normalize_dpn_care_return(state)
    return bool(
        data[CARE_EXAM_REQUIRED]
        or data[CARE_EXAM_REASON]
        or data[CARE_EXAM_DATE]
        or data[CARE_EXAM_RESULT]
        or data[CARE_RETURN_DATE]
        or data[CARE_RETURN_MODE]
    )


def exam_details_relevant(state: dict[str, Any] | None) -> bool:
    return normalize_dpn_care_return(state)[CARE_EXAM_REQUIRED] == EXAM_REQUIRED_YES


def return_date_relevant(state: dict[str, Any] | None) -> bool:
    return normalize_dpn_care_return(state)[CARE_RETURN_MODE] != RETURN_MODE_NOT_STARTED


def apply_dpn_care_return_to_saved_data(
    saved_data: dict[str, Any] | None,
    *,
    accident: AccidentLike | None,
    ui_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Zapíše péči a návrat do JSON šetření. Datum návratu se z ``dpn_do`` neodvozuje."""
    data = dict(saved_data or {})
    existing = dpn_care_return_from_saved_data(data)
    if ui_state is None:
        return data

    normalized = normalize_dpn_care_return(ui_state)
    if dpn_care_return_has_progress(normalized):
        data[DPN_CARE_RETURN_KEY] = normalized
        return data

    dpn_ended = is_dpn_ended(
        getattr(accident, "dpn_do", None) if accident is not None else None
    )
    if not dpn_ended and dpn_care_return_has_progress(existing):
        return data

    data.pop(DPN_CARE_RETURN_KEY, None)
    return data
