"""Formátování plánovaných návštěv programu auditů."""

from __future__ import annotations

from datetime import date

from moduly.audity.constants import (
    AUDIT_PROGRAM_VISIT_SKIPPED_SUFFIX,
    AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_STATUS_SKIPPED,
    MONTH_NAMES_CAPITALIZED,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)
from moduly.audity.modely.audit_program import AuditProgramVisit


def format_czech_date(value: date | None) -> str:
    if value is None:
        return "—"
    return f"{value.day}. {value.month}. {value.year}"


def format_visit_month_label(visit: AuditProgramVisit) -> str:
    month = visit.planned_month or 0
    year = visit.planned_year or 0
    if 1 <= month <= 12:
        return f"{MONTH_NAMES_CAPITALIZED[month - 1]} {year}"
    if year:
        return f"{month}/{year}"
    return PLANNED_MONTH_NOT_SET_LABEL


def format_visit_period_label(visit: AuditProgramVisit) -> str:
    period = format_visit_month_label(visit)
    if visit.planned_date is not None:
        return f"{format_czech_date(visit.planned_date)} — {period}"
    return period


def visit_tree_label(visit: AuditProgramVisit) -> str:
    label = format_visit_period_label(visit)
    if visit.status == AUDIT_PROGRAM_VISIT_STATUS_SKIPPED:
        label = f"{label} {AUDIT_PROGRAM_VISIT_SKIPPED_SUFFIX}"
    elif visit.status == AUDIT_PROGRAM_VISIT_STATUS_COMPLETED:
        label = f"✓ {label}"
    elif visit.audit_id is not None:
        label = f"▶ {label}"
    return label


def visit_sort_key(visit: AuditProgramVisit) -> tuple:
    if visit.planned_date is not None:
        return (0, visit.planned_date.toordinal(), visit.id)
    year = visit.planned_year or 9999
    month = visit.planned_month or 12
    return (1, year * 100 + month, visit.id)


def format_month_name(month: int | None) -> str:
    if month is None or not 1 <= int(month) <= 12:
        return PLANNED_MONTH_NOT_SET_LABEL
    return PLANNED_MONTH_NAMES[int(month) - 1]


def format_planned_term(
    *,
    planned_date: date | None,
    planned_year: int | None,
    planned_month: int | None,
) -> str:
    if planned_date is not None:
        return format_czech_date(planned_date)

    month = planned_month or 0
    year = planned_year or 0
    if 1 <= month <= 12:
        return f"{MONTH_NAMES_CAPITALIZED[month - 1]} {year}"
    if year:
        return f"{month}/{year}"
    return PLANNED_MONTH_NOT_SET_LABEL


def format_visit_term(visit: AuditProgramVisit) -> str:
    return format_planned_term(
        planned_date=visit.planned_date,
        planned_year=visit.planned_year,
        planned_month=visit.planned_month,
    )
