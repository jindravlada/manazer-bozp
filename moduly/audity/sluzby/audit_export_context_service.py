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


def _format_labeled_block(
    index: int,
    title: str,
    fields: list[tuple[str, str]],
) -> str:
    lines = [f"{index}. {title}"]
    for label, value in fields:
        text = _text(value)
        if text:
            lines.append(f"   {label}: {text}")
    return "\n".join(lines)


def _join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(blocks)


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
            lines.append(f"• {member.display_name} – {role}")
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

    def _activity_statistics(self):
        return control_activity_statistics_service.compute(ENTITY_AUDITY, self.audit_id)

    def audited_system_label(self) -> str:
        program = self.program_name()
        if program:
            return program
        audit_type = _text(self.audit.audit_type)
        return audit_type or "Systém managementu BOZP"

    def overall_rating_label(self) -> str:
        stats = self._activity_statistics()
        if stats.ratings_nevyhovuje:
            return "🔴 Nevyhovující"
        if stats.ratings_vyhovuje_s_doporucenim:
            return "🟡 Vyhovuje s výhradami"
        return "🟢 Vyhovující"

    def auditor_recommendation_text(self) -> str:
        stats = self._activity_statistics()
        summary = audit_service.get_conclusion_summary(self.audit_id)
        sentences: list[str] = []

        if stats.ratings_nevyhovuje:
            sentences.append(
                f"Audit identifikoval {stats.ratings_nevyhovuje} neshod "
                "vyžadujících bezodkladné řešení."
            )
        if stats.ratings_vyhovuje_s_doporucenim:
            sentences.append(
                f"V {stats.ratings_vyhovuje_s_doporucenim} oblastech byla "
                "doporučena preventivní zlepšení."
            )
        if not sentences:
            sentences.append(
                "Audit potvrdil účinnost systému managementu BOZP "
                "bez závažných nedostatků."
            )
        if summary["findings_open"] > 0 or summary["tasks_active"] > 0:
            sentences.append(
                f"Organizaci doporučujeme prioritně dokončit "
                f"{summary['findings_open']} otevřených zjištění "
                f"a {summary['tasks_active']} aktivních úkolů."
            )
        else:
            sentences.append(
                "Doporučujeme průběžně sledovat plnění přijatých opatření "
                "a udržovat zavedené kontroly."
            )
        return " ".join(sentences[:4])

    def executive_summary_text(self) -> str:
        stats = self._activity_statistics()
        lines = [
            f"Celkové hodnocení: {self.overall_rating_label()}",
            f"Auditovaný provoz: {_text(self.audit.workplace_name) or '—'}",
            f"Auditovaný systém: {self.audited_system_label()}",
            f"Datum auditu: {_fmt_date(self.audit.audit_date) or '—'}",
            "Auditované procesy:",
            self.processes_text(),
            f"Počet auditních tvrzení: {stats.control_points_checked}",
            f"Počet neshod: {stats.ratings_nevyhovuje}",
            f"Počet doporučení: {stats.ratings_vyhovuje_s_doporucenim}",
            "",
            "Stručné doporučení auditora:",
            self.auditor_recommendation_text(),
        ]
        return "\n".join(lines)

    def results_overview_text(self) -> str:
        stats = self._activity_statistics()
        summary = audit_service.get_conclusion_summary(self.audit_id)
        return "\n".join(
            [
                f"Auditovaných procesů: {len(self.processes_lines())}",
                f"Auditních tvrzení: {stats.control_points_checked}",
                f"Vyhovuje: {stats.ratings_vyhovuje}",
                f"Vyhovuje s doporučením: {stats.ratings_vyhovuje_s_doporucenim}",
                f"Nevyhovuje: {stats.ratings_nevyhovuje}",
                f"Zjištění: {stats.findings_total}",
                f"Úkolů: {summary['tasks_total']}",
            ]
        )

    def signatures_text(self) -> str:
        lines = ["Auditní tým:"]
        commission = self.commission_lines()
        if commission:
            lines.extend(commission)
        else:
            lines.append("Nejsou evidováni.")

        lines.extend(
            [
                "",
                f"Datum vyhotovení protokolu: {datetime.now().strftime('%d.%m.%Y')}",
                "",
                "Podpis vedoucího auditu: _________________________",
                "Podpis zástupce zaměstnavatele: _________________________",
            ]
        )
        return "\n".join(lines)

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
            lines.append(
                _format_labeled_block(
                    index,
                    control_result_label(row.result),
                    [
                        ("Proces", row.source_area_label),
                        ("Kritérium", row.source_section_label),
                        ("Tvrzení", row.source_control_point_label),
                        ("Poznámka", row.note),
                    ],
                )
            )
        return lines

    def evaluation_text(self) -> str:
        lines = self.evaluation_lines()
        return _join_blocks(lines) if lines else "Nejsou evidována významná zjištění."

    def significant_findings_text(self) -> str:
        return self.evaluation_text()

    def findings_lines(self) -> list[str]:
        findings = finding_service.get_for_entity(ENTITY_AUDITY, self.audit_id)
        if not findings:
            return []

        lines: list[str] = []
        for index, finding in enumerate(
            sorted(findings, key=lambda item: (item.display_order, item.id)),
            start=1,
        ):
            lines.append(
                _format_labeled_block(
                    index,
                    finding_type_label(finding.finding_type),
                    [
                        ("Proces", finding.source_area_label),
                        ("Kritérium", finding.source_section_label),
                        ("Popis", finding.description),
                        ("Doporučení", finding.recommended_action),
                        ("Termín", _fmt_date(finding.due_date)),
                        ("Odpovědná osoba", finding.responsible_person_name),
                        ("Stav", finding_status_label(finding.status)),
                    ],
                )
            )
        return lines

    def findings_text(self) -> str:
        lines = self.findings_lines()
        return _join_blocks(lines) if lines else "Nejsou evidována."

    def findings_detail_text(self) -> str:
        return self.findings_text()

    def tasks_lines(self) -> list[str]:
        tasks = audit_service.get_tasks_for_audit(self.audit_id)
        if not tasks:
            return []

        lines: list[str] = []
        for index, task in enumerate(tasks, start=1):
            lines.append(
                _format_labeled_block(
                    index,
                    task.title or "Úkol",
                    [
                        ("Odpovídá", task.responsible_person),
                        ("Termín", _fmt_date(task.due_date)),
                        ("Stav", task.computed_status),
                        ("Splněno", _fmt_date(task.completed_date)),
                    ],
                )
            )
        return lines

    def tasks_text(self) -> str:
        lines = self.tasks_lines()
        return _join_blocks(lines) if lines else "Nejsou evidována."

    def accepted_measures_text(self) -> str:
        return self.tasks_text()

    def statistics_text(self) -> str:
        return self.results_overview_text()

    def summary_text(self) -> str:
        return self.executive_summary_text()

    def conclusion_text(self) -> str:
        summary = audit_service.get_conclusion_summary(self.audit_id)
        stats = self._activity_statistics()

        evaluation_parts: list[str] = []
        if stats.ratings_nevyhovuje:
            evaluation_parts.append(f"{stats.ratings_nevyhovuje} neshod")
        if stats.ratings_vyhovuje_s_doporucenim:
            evaluation_parts.append(
                f"{stats.ratings_vyhovuje_s_doporucenim} oblastí s doporučením"
            )

        if evaluation_parts:
            sentence = (
                "Na základě provedeného interního auditu bylo zjištěno "
                + " a ".join(evaluation_parts)
                + "."
            )
        else:
            sentence = (
                "Na základě provedeného interního auditu nebyly zjištěny "
                "neshody ani doporučení k nápravě."
            )

        if summary["findings_open"] > 0 or summary["tasks_active"] > 0:
            sentence += (
                f" K uzavření zbývá {summary['findings_open']} otevřených zjištění"
                f" a {summary['tasks_active']} aktivních úkolů."
            )
        else:
            sentence += (
                " Zjištěné nedostatky byly zaznamenány a byla přijata "
                "odpovídající nápravná opatření."
            )
        return sentence

    def placeholder_values(self) -> dict[str, str]:
        executive_summary = self.executive_summary_text()
        results_overview = self.results_overview_text()
        significant_findings = self.significant_findings_text()
        accepted_measures = self.accepted_measures_text()
        findings_detail = self.findings_detail_text()
        conclusion = self.conclusion_text()
        signatures = self.signatures_text()

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
            "celkove_hodnoceni": self.overall_rating_label(),
            "auditovany_provoz": _text(self.audit.workplace_name),
            "auditovany_system": self.audited_system_label(),
            "doporuceni_auditora": self.auditor_recommendation_text(),
            "executive_summary_text": executive_summary,
            "prehled_vysledku_text": results_overview,
            "vyznamna_zjisteni_text": significant_findings,
            "prijata_opatreni_text": accepted_measures,
            "detail_zjisteni_text": findings_detail,
            "podpisy_text": signatures,
            "hodnoceni_text": significant_findings,
            "zjisteni_text": findings_detail,
            "ukoly_text": accepted_measures,
            "zaver_text": conclusion,
            "statistika_text": results_overview,
            "souhrn_text": executive_summary,
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
