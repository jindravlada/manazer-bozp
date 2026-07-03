import calendar
import json
from datetime import date

from moduly.nastaveni.constants.workplace_audit_constants import (
    DEFAULT_PREFERRED_AUDIT_MONTHS,
    DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS,
)


def dump_preferred_months(months: list[int] | tuple[int, ...]) -> str:
    normalized = normalize_preferred_months(months)
    return json.dumps(list(normalized), ensure_ascii=False)


def parse_preferred_months_json(json_str: str | None) -> tuple[int, ...]:
    if not json_str or not str(json_str).strip():
        return ()
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    return normalize_preferred_months(parsed)


def normalize_preferred_months(months) -> tuple[int, ...]:
    if not months:
        return ()
    unique = sorted({int(item) for item in months if 1 <= int(item) <= 12})
    return tuple(unique)


def default_preferred_months_json() -> str:
    return dump_preferred_months(DEFAULT_PREFERRED_AUDIT_MONTHS)


def add_months(year: int, month: int, months: int) -> tuple[int, int]:
    total_month_index = year * 12 + (month - 1) + months
    return total_month_index // 12, total_month_index % 12 + 1


def iter_visit_month_anchors(
    date_from: date,
    date_to: date,
    interval_months: int,
) -> list[tuple[int, int]]:
    if interval_months <= 0:
        raise ValueError("Interval auditu pracoviště musí být kladný.")

    slots: list[tuple[int, int]] = []
    year = date_from.year
    month = date_from.month

    while True:
        first_of_month = date(year, month, 1)
        if first_of_month > date_to:
            break

        last_day = calendar.monthrange(year, month)[1]
        last_of_month = date(year, month, last_day)
        if last_of_month >= date_from:
            slots.append((year, month))

        year, month = add_months(year, month, interval_months)

    return slots


def _visit_in_program_range(
    planned_year: int,
    planned_month: int,
    date_from: date,
    date_to: date,
) -> bool:
    first_day = date(planned_year, planned_month, 1)
    if first_day > date_to:
        return False
    last_day = calendar.monthrange(planned_year, planned_month)[1]
    return date(planned_year, planned_month, last_day) >= date_from


def _candidate_months_for_anchor(
    preferred: tuple[int, ...],
    anchor_month: int,
    interval_months: int,
) -> list[int]:
    if interval_months >= 12:
        return list(preferred)

    lower = [month for month in preferred if month < 7]
    upper = [month for month in preferred if month >= 7]
    if not lower:
        lower = list(preferred)
    if not upper:
        upper = list(preferred)

    if anchor_month >= 7:
        return upper
    return lower


def _pick_balanced_month(
    candidates: list[int],
    anchor_year: int,
    date_from: date,
    date_to: date,
    month_usage: dict[tuple[int, int], int],
    workplace_key: int,
    slot_index: int,
) -> tuple[int, int] | None:
    if not candidates:
        return None

    start = (workplace_key + slot_index) % len(candidates)
    ordered = candidates[start:] + candidates[:start]

    options: list[tuple[int, int, int, int, int]] = []
    for rotation, month in enumerate(ordered):
        for year_offset, year in enumerate((anchor_year, anchor_year + 1, anchor_year - 1)):
            if not _visit_in_program_range(year, month, date_from, date_to):
                continue

            usage = month_usage.get((year, month), 0)
            options.append((usage, rotation, year_offset, year, month))

    if not options:
        return None

    options.sort()
    _, _, _, year, month = options[0]
    return year, month


def plan_visit_months(
    date_from: date,
    date_to: date,
    interval_months: int,
    preferred_months: tuple[int, ...],
    *,
    month_usage: dict[tuple[int, int], int] | None = None,
    workplace_key: int = 0,
) -> list[tuple[int, int]]:
    interval = int(interval_months or DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS)
    preferred = normalize_preferred_months(preferred_months)
    anchors = iter_visit_month_anchors(date_from, date_to, interval)
    usage = month_usage if month_usage is not None else {}

    if not preferred:
        return anchors

    planned: list[tuple[int, int]] = []
    for slot_index, (anchor_year, anchor_month) in enumerate(anchors):
        candidates = _candidate_months_for_anchor(preferred, anchor_month, interval)
        chosen = _pick_balanced_month(
            candidates,
            anchor_year,
            date_from,
            date_to,
            usage,
            workplace_key,
            slot_index,
        )
        if chosen is None:
            if _visit_in_program_range(anchor_year, anchor_month, date_from, date_to):
                chosen = (anchor_year, anchor_month)
            else:
                continue

        planned.append(chosen)
        usage[chosen] = usage.get(chosen, 0) + 1

    return planned
