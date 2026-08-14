"""Souhrn mimořádných ověření pro roční / závěrečnou zprávu (AUDIT-EXTRAORDINARY-3)."""

from __future__ import annotations

from collections import Counter

from core.shared.constants import (
    CONTROL_RESULT_NEKONTROLOVANO,
    CONTROL_RESULT_NELZE_POSOUDIT,
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
    ENTITY_AUDITY,
)
from core.shared.control_result_display import control_result_label
from core.shared.sluzby.control_activity_statistics_service import (
    control_activity_statistics_service,
)
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from core.shared.verification_type import (
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_LABELS,
    VERIFICATION_TYPE_TERRAIN,
)
from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    CONTROL_POINT_SEVERITY_OPTIONS,
    EXTRAORDINARY_ANNUAL_SUMMARY_TITLE,
    EXTRAORDINARY_VERIFICATION_TYPE_LEGACY_LABEL,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind
from moduly.audity.sluzby.audit_question_source_service import (
    AuditQuestionSourceError,
    audit_question_source_service,
)
from moduly.audity.sluzby.audit_service import audit_service

_SEVERITY_LABELS = dict(CONTROL_POINT_SEVERITY_OPTIONS)


def build_extraordinary_summary_text(audits: list[Audit]) -> str:
    """Souhrn mimořádných otázek ve rozsahu; prázdný řetězec = sekci nevytvářet."""
    total = 0
    results = Counter()
    severities = Counter()
    verification_types = Counter()
    findings_total = 0
    tasks_total = 0
    tasks_by_status: Counter[str] = Counter()

    for audit in audits:
        if audit is None or not getattr(audit, "id", None):
            continue
        try:
            source = audit_question_source_service.resolve_for_audit(int(audit.id))
        except AuditQuestionSourceError:
            continue
        if not source.is_snapshot:
            continue

        extraordinary_ids: set[str] = set()
        for view in source.assertions:
            if interpret_question_kind(view.question_kind) != AUDIT_QUESTION_KIND_EXTRAORDINARY:
                continue
            total += 1
            extraordinary_ids.add(str(view.assertion_id or "").strip())
            severity_key = str(view.severity or "").strip().lower()
            severities[_SEVERITY_LABELS.get(severity_key, severity_key or "—")] += 1
            frozen = str(view.verification_type or "").strip()
            if frozen == VERIFICATION_TYPE_DOCUMENTATION:
                verification_types[VERIFICATION_TYPE_LABELS[VERIFICATION_TYPE_DOCUMENTATION]] += 1
            elif frozen == VERIFICATION_TYPE_TERRAIN:
                verification_types[VERIFICATION_TYPE_LABELS[VERIFICATION_TYPE_TERRAIN]] += 1
            else:
                verification_types[EXTRAORDINARY_VERIFICATION_TYPE_LEGACY_LABEL] += 1

        if not extraordinary_ids:
            continue

        for row in control_result_service.get_for_entity(ENTITY_AUDITY, int(audit.id)):
            cp_id = str(row.source_control_point_id or "").strip()
            if cp_id not in extraordinary_ids:
                continue
            value = str(row.result or "").strip() or CONTROL_RESULT_NEKONTROLOVANO
            results[control_result_label(value)] += 1

        stats = control_activity_statistics_service.compute(ENTITY_AUDITY, int(audit.id))
        # Zjištění/úkoly navázané na mimořádné assertion_id.
        findings = finding_service.get_for_entity(ENTITY_AUDITY, int(audit.id))
        linked_finding_ids: set[int] = set()
        linked_task_ids: set[int] = set()
        for finding in findings:
            cp_id = str(finding.source_control_point_id or "").strip()
            if cp_id not in extraordinary_ids:
                continue
            findings_total += 1
            linked_finding_ids.add(int(finding.id))
            if getattr(finding, "task_id", None):
                linked_task_ids.add(int(finding.task_id))

        for task in audit_service.get_tasks_for_audit(int(audit.id)):
            if int(getattr(task, "id", 0) or 0) not in linked_task_ids:
                continue
            tasks_total += 1
            status = (
                str(getattr(task, "computed_status", None) or "").strip()
                or str(getattr(task, "status", None) or "").strip()
                or "—"
            )
            tasks_by_status[status] += 1

        # stats unused except to keep import intentional for future weights
        _ = stats

    if total <= 0:
        return ""

    lines = [
        EXTRAORDINARY_ANNUAL_SUMMARY_TITLE,
        f"Celkem mimořádných otázek: {total}",
    ]
    if results:
        lines.append("Výsledky ověření:")
        for label, count in sorted(results.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"  • {label}: {count}")
    if severities:
        lines.append("Závažnost:")
        for label, count in sorted(severities.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"  • {label}: {count}")
    if verification_types:
        lines.append("Typ ověření:")
        for label, count in sorted(
            verification_types.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"  • {label}: {count}")
    lines.append(f"Zjištění: {findings_total}")
    lines.append(f"Úkoly: {tasks_total}")
    if tasks_by_status:
        lines.append("Stavy úkolů:")
        for label, count in sorted(
            tasks_by_status.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"  • {label}: {count}")
    return "\n".join(lines)
