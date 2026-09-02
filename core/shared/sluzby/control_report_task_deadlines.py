"""Souhrn navazujících úkolů a rozhodných termínů pro úvod kontrolních zpráv.

Bez Qt. Nečte databázi — pracuje s už načtenými Finding a dávkou Task.
Otevřený úkol = computed_status není Ukončeno ani Zrušeno.
Rozhodný termín = task_urgency_due_date (stejně jako Agenda a dashboard).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from core.utils.czech_count import format_czech_count
from moduly.ukoly.constants import TASK_STATUS_CANCELED, TASK_STATUS_CLOSED
from moduly.ukoly.sluzby.task_deadline import task_urgency_due_date

logger = logging.getLogger(__name__)

TERMINAL_TASK_STATUSES = frozenset({TASK_STATUS_CLOSED, TASK_STATUS_CANCELED})

OPEN_TASKS_OVERVIEW_LABEL = "Otevřené úkoly"
LATEST_DUE_OVERVIEW_LABEL = "Nejzazší evidovaný termín"
OPEN_WITHOUT_DUE_OVERVIEW_LABEL = "Otevřené úkoly bez termínu"

NO_LINKED_TASKS_SENTENCE = (
    "Ke zjištěním nejsou evidovány žádné navazující úkoly."
)
ALL_TASKS_TERMINAL_SENTENCE = (
    "Všechny evidované navazující úkoly jsou ukončené nebo zrušené."
)

OPEN_FOLLOWUP_TASK_FORMS = {
    "one": "otevřený navazující úkol",
    "few": "otevřené navazující úkoly",
    "many": "otevřených navazujících úkolů",
}


@dataclass(frozen=True)
class LinkedTasksDeadlineSummary:
    """Read-only souhrn Task navázaných přes Finding.task_id."""

    finding_count: int
    linked_task_count: int
    open_count: int
    terminal_count: int
    open_without_due_count: int
    latest_due_date: date | None
    missing_task_link_count: int

    def all_open_have_due(self) -> bool:
        return self.open_count > 0 and self.open_without_due_count == 0


def is_open_followup_task(task) -> bool:
    """Stejný význam jako tasks_active v get_conclusion_summary."""
    status = str(getattr(task, "computed_status", "") or "")
    return status not in TERMINAL_TASK_STATUSES


def format_report_date(value: date) -> str:
    """České datum ve stejném pořadí d. m. r. jako v exportech."""
    return value.strftime("%d. %m. %Y")


def summarize_linked_task_deadlines(
    findings: Sequence,
    tasks_by_id: Mapping[int, object],
    *,
    log_missing: bool = True,
) -> LinkedTasksDeadlineSummary:
    """Spočítá existující Task podle Finding.task_id. Chybějící vazby nepočítá."""
    seen_task_ids: set[int] = set()
    existing: list[object] = []
    missing = 0
    for finding in findings:
        raw = getattr(finding, "task_id", None)
        if not raw:
            continue
        task_id = int(raw)
        if task_id in seen_task_ids:
            continue
        seen_task_ids.add(task_id)
        task = tasks_by_id.get(task_id)
        if task is None:
            missing += 1
            if log_missing:
                finding_id = getattr(finding, "id", None)
                logger.warning(
                    "Finding %s odkazuje na neexistující úkol task_id=%s",
                    finding_id,
                    task_id,
                )
            continue
        existing.append(task)

    open_tasks = [task for task in existing if is_open_followup_task(task)]
    due_dates: list[date] = []
    without_due = 0
    for task in open_tasks:
        decisive = task_urgency_due_date(task)
        if decisive is None:
            without_due += 1
        else:
            due_dates.append(decisive)

    latest = max(due_dates) if open_tasks and without_due == 0 and due_dates else None
    return LinkedTasksDeadlineSummary(
        finding_count=len(findings),
        linked_task_count=len(existing),
        open_count=len(open_tasks),
        terminal_count=len(existing) - len(open_tasks),
        open_without_due_count=without_due,
        latest_due_date=latest,
        missing_task_link_count=missing,
    )


def format_linked_tasks_overview_lines(
    summary: LinkedTasksDeadlineSummary,
) -> list[str]:
    """Řádky Přehledu výsledků. Otevřené úkoly vždy; termín jen když je jednoznačný."""
    lines = [f"{OPEN_TASKS_OVERVIEW_LABEL}: {summary.open_count}"]
    if summary.open_count == 0:
        return lines
    if summary.open_without_due_count:
        lines.append(
            f"{OPEN_WITHOUT_DUE_OVERVIEW_LABEL}: {summary.open_without_due_count}"
        )
        return lines
    if summary.latest_due_date is not None:
        lines.append(
            f"{LATEST_DUE_OVERVIEW_LABEL}: {format_report_date(summary.latest_due_date)}"
        )
    return lines


def format_linked_tasks_assessment_sentence(
    summary: LinkedTasksDeadlineSummary,
) -> str:
    """Věta do CELKOVÉHO HODNOCENÍ, nebo prázdný řetězec bez Finding i Task."""
    if summary.finding_count == 0 and summary.linked_task_count == 0:
        return ""
    if summary.open_count > 0:
        counted = format_czech_count(summary.open_count, **OPEN_FOLLOWUP_TASK_FORMS)
        head = f"Evidence obsahuje {counted}"
        if summary.open_without_due_count:
            if summary.open_without_due_count == 1:
                rest = "1 z nich nemá stanovený termín."
            else:
                rest = (
                    f"{summary.open_without_due_count} z nich nemají stanovený termín."
                )
            return f"{head}; {rest}"
        if summary.latest_due_date is not None:
            latest = format_report_date(summary.latest_due_date)
            return (
                f"{head}. Nejzazší evidovaný termín otevřených úkolů je {latest}."
            )
        return f"{head}."
    if summary.linked_task_count > 0:
        return ALL_TASKS_TERMINAL_SENTENCE
    if summary.finding_count > 0:
        return NO_LINKED_TASKS_SENTENCE
    return ""
