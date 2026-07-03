from dataclasses import dataclass
from datetime import date, datetime

from core.shared.constants import ENTITY_AUDITY
from core.shared.control_result_display import control_result_label, protocol_evaluation_results
from core.shared.finding_display import finding_status_label, finding_type_label
from core.shared.sluzby.control_activity_statistics_service import (
    control_activity_statistics_service,
)
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from moduly.audity.constants import (
    COMMISSION_RECORD_INVITED,
    COMMISSION_RECORD_LEADER,
    COMMISSION_RECORD_MEMBER,
    COMMISSION_RECORD_UNION,
    COMMISSION_RECORD_WORKPLACE,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.repository.audit_program_repository import AuditProgramRepository
from moduly.audity.sluzby.audit_commission_service import audit_commission_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_service import audit_service
from moduly.nastaveni.sluzby.settings_service import settings_service


def _fmt_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text).strftime("%d.%m.%Y")
    except Exception:
        return text


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


_COMMISSION_ROLE_LABELS = {
    COMMISSION_RECORD_LEADER: "Vedoucí komise",
    COMMISSION_RECORD_WORKPLACE: "Zástupce pracoviště",
    COMMISSION_RECORD_UNION: "Zástupce odborové organizace",
    COMMISSION_RECORD_MEMBER: "Člen komise",
    COMMISSION_RECORD_INVITED: "Přizvaná osoba",
}

_COMMISSION_EXPORT_ORDER = {
    COMMISSION_RECORD_LEADER: 1,
    COMMISSION_RECORD_WORKPLACE: 2,
    COMMISSION_RECORD_UNION: 3,
    COMMISSION_RECORD_MEMBER: 4,
    COMMISSION_RECORD_INVITED: 5,
}


@dataclass(frozen=True)
class AuditExportContext:
    """Sjednocený kontext exportu protokolu auditu."""

    audit: Audit

    @property
    def audit_id(self) -> int:
        return self.audit.id

    def is_completed(self) -> bool:
        return self.audit.finished_at is not None

    def planned_month_label(self) -> str:
        month = self.audit.planned_month
        if month is None or month < 1 or month > 12:
            return PLANNED_MONTH_NOT_SET_LABEL
        return PLANNED_MONTH_NAMES[month - 1]

    def status_label(self) -> str:
        return audit_service.derive_status(
            self.audit.started_at,
            self.audit.finished_at,
        )

    def employer_name(self) -> str:
        employer = settings_service.get_employer()
        if employer is None:
            return ""
        return _text(employer.name)

    def program_name(self) -> str:
        program_id = self.audit.program_id
        if program_id is None:
            return ""
        program = AuditProgramRepository().get_program(program_id)
        if program is None:
            return ""
        return _text(program.name)

    def commission_lines(self) -> list[str]:
        members = audit_commission_service.get_for_audit(self.audit_id)
        if not members:
            return []

        lines: list[str] = []
        for member in sorted(
            members,
            key=lambda item: (
                _COMMISSION_EXPORT_ORDER.get(item.record_type, 99),
                item.display_order,
                item.id,
            ),
        ):
            role = _COMMISSION_ROLE_LABELS.get(member.record_type, member.record_type)
            parts = [f"• {member.display_name} ({role})"]
            if member.role_text:
                parts.append(f"role: {member.role_text}")
            if member.note_text:
                parts.append(f"poznámka: {member.note_text}")
            lines.append("; ".join(parts))
        return lines

    def commission_text(self) -> str:
        lines = self.commission_lines()
        return "\n".join(lines) if lines else "Nejsou evidováni."

    def planned_process_ids(self) -> tuple[str, ...]:
        visit_id = self.audit.program_visit_id
        if visit_id is None:
            return ()
        visit_context = audit_program_service.get_visit_audit_context(visit_id)
        if visit_context is None:
            return ()
        return visit_context.planned_process_ids

    def processes_lines(self) -> list[str]:
        planned_ids = set(self.planned_process_ids())
        process_names: list[str] = []
        for process in audit_knowledge_service.get_processes():
            if planned_ids and process.id not in planned_ids:
                continue
            process_names.append(process.nazev)
        if process_names:
            return process_names

        seen: set[str] = set()
        for result in control_result_service.get_for_entity(ENTITY_AUDITY, self.audit_id):
            process_id = str(result.source_area_id or "").strip()
            if not process_id or process_id in seen:
                continue
            label = str(result.source_area_label or process_id).strip() or process_id
            seen.add(process_id)
            process_names.append(label)
        return sorted(process_names, key=str.casefold)

    def processes_text(self) -> str:
        lines = self.processes_lines()
        if not lines:
            return "Nejsou evidovány."
        return "\n".join(f"• {line}" for line in lines)

    def evaluation_lines(self) -> list[str]:
        results = control_result_service.get_for_entity(ENTITY_AUDITY, self.audit_id)
        if not results:
            return []

        included_results = protocol_evaluation_results()
        lines: list[str] = []
        for index, row in enumerate(
            sorted(
                (
                    item
                    for item in results
                    if item.result in included_results
                ),
                key=lambda item: (
                    item.source_area_label,
                    item.source_section_label,
                    item.source_control_point_label,
                    item.id,
                ),
            ),
            start=1,
        ):
            parts = [f"{index}. {control_result_label(row.result)}"]
            if row.source_area_label:
                parts.append(f"proces: {row.source_area_label}")
            if row.source_section_label:
                parts.append(f"kritérium: {row.source_section_label}")
            if row.source_control_point_label:
                parts.append(f"tvrzení: {row.source_control_point_label}")
            if row.note:
                parts.append(f"poznámka: {_text(row.note)}")
            lines.append("; ".join(parts))
        return lines

    def evaluation_text(self) -> str:
        lines = self.evaluation_lines()
        return "\n".join(lines) if lines else "Nejsou evidována."

    def findings_lines(self) -> list[str]:
        findings = finding_service.get_for_entity(ENTITY_AUDITY, self.audit_id)
        if not findings:
            return []

        lines: list[str] = []
        for index, finding in enumerate(
            sorted(findings, key=lambda item: (item.display_order, item.id)),
            start=1,
        ):
            parts = [f"{index}. {finding_type_label(finding.finding_type)}"]
            if finding.source_area_label:
                parts.append(f"proces: {finding.source_area_label}")
            if finding.source_section_label:
                parts.append(f"kritérium: {finding.source_section_label}")
            if finding.source_control_point_label:
                parts.append(f"tvrzení: {finding.source_control_point_label}")
            if finding.reference_label:
                parts.append(f"reference: {finding.reference_label}")
            if finding.description:
                parts.append(f"popis: {_text(finding.description)}")
            parts.append(f"stav: {finding_status_label(finding.status)}")
            if finding.recommended_action:
                parts.append(f"doporučení: {_text(finding.recommended_action)}")
            if finding.due_date:
                parts.append(f"termín: {_fmt_date(finding.due_date)}")
            if finding.responsible_person_name:
                parts.append(f"odpovědná osoba: {finding.responsible_person_name}")
            lines.append("; ".join(parts))
        return lines

    def findings_text(self) -> str:
        lines = self.findings_lines()
        return "\n".join(lines) if lines else "Nejsou evidována."

    def tasks_lines(self) -> list[str]:
        tasks = audit_service.get_tasks_for_audit(self.audit_id)
        if not tasks:
            return []

        lines: list[str] = []
        for index, task in enumerate(tasks, start=1):
            parts = [f"{index}. {task.title or 'Úkol'}"]
            if task.responsible_person:
                parts.append(f"odpovídá: {task.responsible_person}")
            if task.due_date:
                parts.append(f"termín: {_fmt_date(task.due_date)}")
            parts.append(f"stav: {task.computed_status}")
            if task.completed_date:
                parts.append(f"splněno: {_fmt_date(task.completed_date)}")
            if task.note:
                parts.append(f"poznámka: {_text(task.note)}")
            lines.append("; ".join(parts))
        return lines

    def tasks_text(self) -> str:
        lines = self.tasks_lines()
        return "\n".join(lines) if lines else "Nejsou evidována."

    def statistics_text(self) -> str:
        stats = control_activity_statistics_service.compute(ENTITY_AUDITY, self.audit_id)
        return stats.format_text()

    def conclusion_text(self) -> str:
        process_names = self.processes_lines()
        if process_names:
            areas = ", ".join(process_names)
            return (
                "Na základě provedeného interního auditu bylo ověřeno plnění požadavků "
                f"z oblastí: {areas}. Zjištěné nedostatky byly zaznamenány a byla "
                "přijata odpovídající nápravná opatření."
            )
        return (
            "Na základě provedeného interního auditu byly zjištěné nedostatky "
            "zaznamenány a byla přijata odpovídající nápravná opatření."
        )

    def summary_text(self) -> str:
        summary = audit_service.get_conclusion_summary(self.audit_id)
        return (
            f"{self.statistics_text()}\n\n"
            f"Otevřená zjištění: {summary['findings_open']}\n"
            f"Aktivní úkoly: {summary['tasks_active']}\n"
            f"Stav auditu: {self.status_label()}"
        )

    def placeholder_values(self) -> dict[str, str]:
        return {
            "cislo_auditu": _text(self.audit.number),
            "zamestnavatel_nazev": self.employer_name(),
            "pracoviste": _text(self.audit.workplace_name),
            "provoz": _text(self.audit.workplace_name),
            "program_nazev": self.program_name(),
            "rok": str(self.audit.year or ""),
            "planovany_mesic": self.planned_month_label(),
            "typ_auditu": _text(self.audit.audit_type),
            "datum_auditu": _fmt_date(self.audit.audit_date),
            "datum_zahajeni": _fmt_date(self.audit.started_at),
            "datum_ukonceni": _fmt_date(self.audit.finished_at),
            "stav": self.status_label(),
            "komise_text": self.commission_text(),
            "auditni_tym_text": self.commission_text(),
            "procesy_text": self.processes_text(),
            "hodnoceni_text": self.evaluation_text(),
            "zjisteni_text": self.findings_text(),
            "ukoly_text": self.tasks_text(),
            "zaver_text": self.conclusion_text(),
            "statistika_text": self.statistics_text(),
            "souhrn_text": self.summary_text(),
            "datum_vygenerovani": datetime.now().strftime("%d.%m.%Y"),
        }


class AuditExportContextService:
    def build(self, audit: Audit) -> AuditExportContext:
        if audit is None or not getattr(audit, "id", None):
            raise ValueError("Není vybraný uložený audit.")
        return AuditExportContext(audit=audit)

    def is_completed(self, audit: Audit) -> bool:
        return AuditExportContext(audit=audit).is_completed()


audit_export_context_service = AuditExportContextService()
