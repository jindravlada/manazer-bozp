"""Textové sekce Úvod / Návaznost pro exporty (AUDIT-INTRO-2).

Používá AuditHistoryService (batch, bez zápisu do DB).
Sekce Úvod se nepropsuje do Protokolu auditu ani terénního checklistu.

Text „Změny od posledního auditu“ sem nepatří. Je to samostatná sekce
obou výstupů auditu (protokol i podrobná zpráva), hned pod tabulkou komise.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from moduly.audity.constants import (
    AUDIT_INTRO_EXPORT_FINDINGS_HEADING,
    AUDIT_INTRO_EXPORT_PREVIOUS_AUDITS_HEADING,
    AUDIT_INTRO_EXPORT_TASKS_HEADING,
    AUDIT_INTRO_FIRST_AUDIT_MESSAGE,
    AUDIT_INTRO_NO_HISTORICAL_FINDINGS,
    AUDIT_INTRO_NO_HISTORICAL_TASKS,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.sluzby.audit_history_service import (
    WorkplaceHistory,
    WorkplaceHistoryContinuityAggregate,
    audit_history_service,
)


def _fmt_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    return value.strftime("%d.%m.%Y")


def _labeled_block(index: int, title: str, fields: list[tuple[str, str]]) -> str:
    lines = [f"{index}. {title}"]
    for label, value in fields:
        text = str(value or "").strip() or "—"
        lines.append(f"   {label}: {text}")
    return "\n".join(lines)


def format_detailed_intro_section(
    *,
    history: WorkplaceHistory,
) -> str:
    """Sekce Úvod pro podrobnou zprávu — historie provozu bez textu změn.

    Text změn od posledního auditu se exportuje samostatně, aby se v dokumentu
    neopakoval a při prázdné hodnotě nevznikl nadpis.
    """
    blocks: list[str] = []

    if history.is_first_audit:
        return AUDIT_INTRO_FIRST_AUDIT_MESSAGE

    audit_lines = [
        _labeled_block(
            index,
            item.audit_number,
            [
                ("Datum", _fmt_date(item.audit_date)),
                ("Stav", item.status),
                ("Typ auditu", item.audit_type),
                ("Program auditů", item.program_name),
            ],
        )
        for index, item in enumerate(history.previous_audits, start=1)
    ]
    blocks.append(
        f"{AUDIT_INTRO_EXPORT_PREVIOUS_AUDITS_HEADING}\n\n" + "\n\n".join(audit_lines)
    )

    if history.findings:
        finding_lines = [
            _labeled_block(
                index,
                item.title,
                [
                    ("Stav", item.status_label),
                    ("Závažnost / typ", item.severity_label),
                    ("Původní audit", item.audit_number),
                    ("Datum vzniku", _fmt_date(item.created_at)),
                    ("Datum vypořádání", _fmt_date(item.resolved_at)),
                ],
            )
            for index, item in enumerate(history.findings, start=1)
        ]
        findings_body = "\n\n".join(finding_lines)
    else:
        findings_body = AUDIT_INTRO_NO_HISTORICAL_FINDINGS
    blocks.append(f"{AUDIT_INTRO_EXPORT_FINDINGS_HEADING}\n\n{findings_body}")

    if history.tasks:
        task_lines = [
            _labeled_block(
                index,
                item.title,
                [
                    ("Stav", item.status_label),
                    ("Odpovědná osoba", item.responsible_person),
                    ("Termín", _fmt_date(item.due_date)),
                    ("Datum dokončení / zrušení", _fmt_date(item.completed_date)),
                    (
                        "Původní zjištění / audit",
                        f"{item.finding_title} ({item.audit_number})",
                    ),
                ],
            )
            for index, item in enumerate(history.tasks, start=1)
        ]
        tasks_body = "\n\n".join(task_lines)
    else:
        tasks_body = AUDIT_INTRO_NO_HISTORICAL_TASKS
    blocks.append(f"{AUDIT_INTRO_EXPORT_TASKS_HEADING}\n\n{tasks_body}")

    return "\n\n".join(blocks)


def format_continuity_aggregate(
    aggregate: WorkplaceHistoryContinuityAggregate,
) -> str:
    """Stručné souhrnné počty pro roční / závěrečnou zprávu."""
    return "\n".join(
        [
            f"Počet dohledaných předchozích auditů: {aggregate.previous_audits_count}",
            f"Počet historických zjištění celkem: {aggregate.findings_total_count}",
            (
                "Počet nevypořádaných historických zjištění: "
                f"{aggregate.findings_open_count}"
            ),
            (
                "Počet vypořádaných historických zjištění: "
                f"{aggregate.findings_resolved_count}"
            ),
            f"Počet historických úkolů celkem: {aggregate.tasks_total_count}",
            (
                "Počet aktivních/nesplněných historických úkolů: "
                f"{aggregate.tasks_active_count}"
            ),
            f"Počet dokončených historických úkolů: {aggregate.tasks_completed_count}",
            f"Počet zrušených historických úkolů: {aggregate.tasks_canceled_count}",
        ]
    )


class AuditIntroExportService:
    def build_detailed_intro_text(self, audit: Audit) -> str:
        history = audit_history_service.get_workplace_history(
            getattr(audit, "workplace_id", None),
            current_audit=audit,
            include_process_history=False,
        )
        return format_detailed_intro_section(history=history)

    def build_continuity_text_for_audits(self, audits: Sequence[Audit]) -> str:
        aggregate = audit_history_service.aggregate_continuity_for_audits(audits)
        return format_continuity_aggregate(aggregate)


audit_intro_export_service = AuditIntroExportService()
