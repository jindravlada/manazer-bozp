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


def _closest_index(group: list[int], target: int) -> int:
    if not group:
        return 0

    best_index = 0
    best_distance = 13
    for index, month in enumerate(group):
        distance = min(abs(month - target), 12 - abs(month - target))
        if distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index


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


def plan_visit_months(
    date_from: date,
    date_to: date,
    interval_months: int,
    preferred_months: tuple[int, ...],
) -> list[tuple[int, int]]:
    interval = int(interval_months or DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS)
    preferred = normalize_preferred_months(preferred_months)
    anchors = iter_visit_month_anchors(date_from, date_to, interval)

    if not preferred:
        return anchors

    sorted_pref = sorted(preferred)
    start = _closest_index(sorted_pref, date_from.month)

    if interval >= 12:
        planned: list[tuple[int, int]] = []
        for index, (anchor_year, _anchor_month) in enumerate(anchors):
            chosen_month = sorted_pref[(start + index) % len(sorted_pref)]
            chosen_year = anchor_year
            if not _visit_in_program_range(chosen_year, chosen_month, date_from, date_to):
                continue
            planned.append((chosen_year, chosen_month))
        return planned

    lower = [month for month in preferred if month < 7]
    upper = [month for month in preferred if month >= 7]
    if not lower:
        lower = list(preferred)
    if not upper:
        upper = list(preferred)

    lower_start = _closest_index(lower, date_from.month)
    upper_start = _closest_index(upper, 10)

    lower_slot_count = 0
    upper_slot_count = 0
    planned: list[tuple[int, int]] = []

    for anchor_year, anchor_month in anchors:
        fiscal_year_index = anchor_year - date_from.year
        if anchor_year == date_from.year and anchor_month < date_from.month:
            fiscal_year_index -= 1

        if anchor_month >= 7:
            group = upper
            start = upper_start
            upper_slot_count += 1
            month_index = (start + fiscal_year_index) % len(group)
        else:
            group = lower
            start = lower_start
            lower_slot_count += 1
            month_index = (start - fiscal_year_index) % len(group)

        chosen_month = group[month_index]
        chosen_year = anchor_year

        if not _visit_in_program_range(chosen_year, chosen_month, date_from, date_to):
            if _visit_in_program_range(chosen_year + 1, chosen_month, date_from, date_to):
                chosen_year += 1
            elif _visit_in_program_range(chosen_year, anchor_month, date_from, date_to):
                chosen_month = anchor_month
            else:
                continue

        planned.append((chosen_year, chosen_month))

    return planned
