"""Péče a návrat do práce po ukončení DPN – JSON šetření, bez zdravotních diagnóz."""

from __future__ import annotations

from typing import Any

from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    AccidentLike,
    add_workdays,
    dpn_calendar_days,
    is_dpn_ended,
    parse_saved_date,
)


DPN_CARE_RETURN_KEY = "dpn_care_return"

CARE_EXAM_REQUIRED = "exam_required"
CARE_EXAM_REASON = "exam_reason"
CARE_EXAM_DATE = "exam_date"
CARE_EXAM_RESULT = "exam_result"
CARE_EXAM_DEADLINE = "exam_deadline"
CARE_DPN_OVER_8_WEEKS = "dpn_over_8_weeks"
CARE_CATEGORY_1_NO_RISK = "category_1_no_risk"
CARE_SEVERE_CONSEQUENCES = "severe_consequences"
CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM = "unconsciousness_or_severe_harm"
CARE_FITNESS_CHANGE_PRESUMED = "fitness_change_presumed"
CARE_RETURN_DATE = "return_date"
CARE_RETURN_MODE = "return_mode"

EXAM_REQUIRED_YES = "ANO"
EXAM_REQUIRED_NO = "NE"

EXAM_REQUIRED_BANNER_YES = (
    "Mimořádná pracovnělékařská prohlídka JE VYŽADOVÁNA"
)
EXAM_REQUIRED_BANNER_NO = (
    "Mimořádná pracovnělékařská prohlídka NENÍ VYŽADOVÁNA"
)

# Osm týdnů kalendářně; důvodem je přerušení delší než tato hranice.
DPN_EXTRAORDINARY_EXAM_AFTER_DAYS = 56
EXAM_DEADLINE_WORKDAYS = 5

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

_USER_PROGRESS_KEYS = (
    CARE_EXAM_REASON,
    CARE_EXAM_DATE,
    CARE_EXAM_RESULT,
    CARE_CATEGORY_1_NO_RISK,
    CARE_SEVERE_CONSEQUENCES,
    CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM,
    CARE_FITNESS_CHANGE_PRESUMED,
    CARE_RETURN_DATE,
    CARE_RETURN_MODE,
)


def empty_dpn_care_return() -> dict[str, Any]:
    return {
        CARE_EXAM_REQUIRED: "",
        CARE_EXAM_REASON: "",
        CARE_EXAM_DATE: None,
        CARE_EXAM_RESULT: "",
        CARE_EXAM_DEADLINE: None,
        CARE_DPN_OVER_8_WEEKS: "",
        CARE_CATEGORY_1_NO_RISK: "",
        CARE_SEVERE_CONSEQUENCES: "",
        CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM: "",
        CARE_FITNESS_CHANGE_PRESUMED: "",
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


def dpn_longer_than_8_weeks(dpn_od: Any = None, dpn_do: Any = None) -> bool:
    days = dpn_calendar_days(parse_saved_date(dpn_od), parse_saved_date(dpn_do))
    return days is not None and days > DPN_EXTRAORDINARY_EXAM_AFTER_DAYS


def exam_deadline_from_return_date(return_date: Any) -> str | None:
    parsed = parse_saved_date(return_date)
    if parsed is None:
        return None
    return add_workdays(parsed, EXAM_DEADLINE_WORKDAYS).isoformat()


def extraordinary_exam_required(
    state: dict[str, Any] | None,
    *,
    dpn_od: Any = None,
    dpn_do: Any = None,
) -> bool:
    data = normalize_dpn_care_return(state)
    duration_reason = dpn_longer_than_8_weeks(
        dpn_od, dpn_do
    ) and data[CARE_CATEGORY_1_NO_RISK] != EXAM_REQUIRED_YES
    return bool(
        duration_reason
        or data[CARE_SEVERE_CONSEQUENCES] == EXAM_REQUIRED_YES
        or data[CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM] == EXAM_REQUIRED_YES
        or data[CARE_FITNESS_CHANGE_PRESUMED] == EXAM_REQUIRED_YES
    )


def exam_required_banner_text(required: bool) -> str:
    if required:
        return EXAM_REQUIRED_BANNER_YES
    return EXAM_REQUIRED_BANNER_NO


def normalize_dpn_care_return(state: dict[str, Any] | None) -> dict[str, Any]:
    data = state if isinstance(state, dict) else {}
    return {
        CARE_EXAM_REQUIRED: _normalize_exam_required(data.get(CARE_EXAM_REQUIRED)),
        CARE_EXAM_REASON: str(data.get(CARE_EXAM_REASON) or "").strip(),
        CARE_EXAM_DATE: _date_json(data.get(CARE_EXAM_DATE)),
        CARE_EXAM_RESULT: _normalize_choice(data.get(CARE_EXAM_RESULT), EXAM_RESULTS),
        CARE_EXAM_DEADLINE: _date_json(data.get(CARE_EXAM_DEADLINE)),
        CARE_DPN_OVER_8_WEEKS: _normalize_exam_required(
            data.get(CARE_DPN_OVER_8_WEEKS)
        ),
        CARE_CATEGORY_1_NO_RISK: _normalize_exam_required(
            data.get(CARE_CATEGORY_1_NO_RISK)
        ),
        CARE_SEVERE_CONSEQUENCES: _normalize_exam_required(
            data.get(CARE_SEVERE_CONSEQUENCES)
        ),
        CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM: _normalize_exam_required(
            data.get(CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM)
        ),
        CARE_FITNESS_CHANGE_PRESUMED: _normalize_exam_required(
            data.get(CARE_FITNESS_CHANGE_PRESUMED)
        ),
        CARE_RETURN_DATE: _date_json(data.get(CARE_RETURN_DATE)),
        CARE_RETURN_MODE: _normalize_choice(data.get(CARE_RETURN_MODE), RETURN_MODES),
    }


def evaluate_dpn_care_return(
    state: dict[str, Any] | None,
    *,
    dpn_od: Any = None,
    dpn_do: Any = None,
) -> dict[str, Any]:
    data = normalize_dpn_care_return(state)
    over = dpn_longer_than_8_weeks(dpn_od, dpn_do)
    data[CARE_DPN_OVER_8_WEEKS] = (
        EXAM_REQUIRED_YES if over else EXAM_REQUIRED_NO
    )
    required = extraordinary_exam_required(
        data, dpn_od=dpn_od, dpn_do=dpn_do
    )
    data[CARE_EXAM_REQUIRED] = (
        EXAM_REQUIRED_YES if required else EXAM_REQUIRED_NO
    )
    if required and return_date_relevant(data):
        data[CARE_EXAM_DEADLINE] = exam_deadline_from_return_date(
            data[CARE_RETURN_DATE]
        )
    else:
        data[CARE_EXAM_DEADLINE] = None
    return data


def dpn_care_return_from_saved_data(saved_data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(saved_data, dict):
        return empty_dpn_care_return()
    raw = saved_data.get(DPN_CARE_RETURN_KEY)
    if not isinstance(raw, dict):
        return empty_dpn_care_return()
    return normalize_dpn_care_return(raw)


def dpn_care_return_has_progress(state: dict[str, Any] | None) -> bool:
    data = normalize_dpn_care_return(state)
    return any(data[key] for key in _USER_PROGRESS_KEYS)


def exam_details_relevant(
    state: dict[str, Any] | None,
    *,
    dpn_od: Any = None,
    dpn_do: Any = None,
) -> bool:
    return evaluate_dpn_care_return(
        state, dpn_od=dpn_od, dpn_do=dpn_do
    )[CARE_EXAM_REQUIRED] == EXAM_REQUIRED_YES


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

    dpn_od = getattr(accident, "dpn_od", None) if accident is not None else None
    dpn_do = getattr(accident, "dpn_do", None) if accident is not None else None
    evaluated = evaluate_dpn_care_return(
        ui_state, dpn_od=dpn_od, dpn_do=dpn_do
    )
    if not evaluated[CARE_EXAM_REASON] and existing[CARE_EXAM_REASON]:
        evaluated[CARE_EXAM_REASON] = existing[CARE_EXAM_REASON]
    if dpn_care_return_has_progress(evaluated):
        data[DPN_CARE_RETURN_KEY] = evaluated
        return data

    dpn_ended = is_dpn_ended(dpn_do)
    if not dpn_ended and dpn_care_return_has_progress(existing):
        return data

    data.pop(DPN_CARE_RETURN_KEY, None)
    return data
