from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.shared.constants import (
    CONTROL_RESULT_NEKONTROLOVANO,
    ENTITY_AUDITY,
    FINDING_STATUS_VYPORADANO,
)
from core.shared.finding_display import finding_status_label, finding_type_label
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from moduly.audity.constants import (
    AUDIT_FINDING_TYPE_LABELS,
    AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
    COMMISSION_RECORD_LEADER,
    MONTH_NAMES_CAPITALIZED,
)
from moduly.audity.repository.audit_program_repository import AuditProgramRepository
from moduly.audity.repository.audit_repository import AuditRepository
from moduly.audity.sluzby.audit_commission_service import audit_commission_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_service import audit_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.task_display import task_description_table_text


@dataclass(frozen=True)
class WorkplaceLastAuditSummary:
    audit_id: int
    audit_number: str
    audit_date: date | None
    leader_name: str
    conclusion: str


@dataclass(frozen=True)
class WorkplaceFindingHistoryItem:
    finding_id: int
    title: str
    severity_label: str
    due_date: date | None
    status_label: str
    audit_id: int
    audit_number: str


@dataclass(frozen=True)
class WorkplaceTaskHistoryItem:
    task_id: int
    title: str
    responsible_person: str
    due_date: date | None
    completion_label: str


@dataclass(frozen=True)
class WorkplaceProcessHistoryItem:
    process_id: str
    process_name: str
    last_audit_label: str
    last_audit_date: date | None


@dataclass(frozen=True)
class WorkplaceHistorySummary:
    last_audit_date: date | None
    open_findings_count: int
    open_tasks_count: int
    audited_processes_count: int
    total_processes_count: int


@dataclass(frozen=True)
class WorkplaceHistory:
    last_audit: WorkplaceLastAuditSummary | None
    findings: tuple[WorkplaceFindingHistoryItem, ...]
    tasks: tuple[WorkplaceTaskHistoryItem, ...]
    process_history: tuple[WorkplaceProcessHistoryItem, ...]
    summary: WorkplaceHistorySummary


class AuditHistoryService:
    def __init__(self) -> None:
        self.audit_repository = AuditRepository()
        self.program_repository = AuditProgramRepository()

    def get_workplace_history(
        self,
        workplace_id: int | None,
        *,
        exclude_audit_id: int | None = None,
    ) -> WorkplaceHistory:
        if workplace_id is None:
            return self._empty_history()

        audits = self.audit_repository.list_for_workplace(
            workplace_id,
            exclude_audit_id=exclude_audit_id,
        )
        last_audit = self._build_last_audit_summary(audits[0]) if audits else None
        findings = self._collect_open_findings(audits)
        tasks = self._collect_open_tasks(audits, findings)
        process_history = self._build_process_history(workplace_id, audits)
        summary = self._build_summary(last_audit, findings, tasks, process_history)
        return WorkplaceHistory(
            last_audit=last_audit,
            findings=tuple(findings),
            tasks=tuple(tasks),
            process_history=tuple(process_history),
            summary=summary,
        )

    def _empty_history(self) -> WorkplaceHistory:
        summary = WorkplaceHistorySummary(
            last_audit_date=None,
            open_findings_count=0,
            open_tasks_count=0,
            audited_processes_count=0,
            total_processes_count=len(audit_knowledge_service.get_processes()),
        )
        return WorkplaceHistory(
            last_audit=None,
            findings=(),
            tasks=(),
            process_history=(),
            summary=summary,
        )

    def _build_last_audit_summary(self, audit) -> WorkplaceLastAuditSummary:
        leader_name = self._leader_name(audit.id)
        conclusion = self._audit_conclusion(audit)
        return WorkplaceLastAuditSummary(
            audit_id=audit.id,
            audit_number=str(audit.number or "").strip() or str(audit.id),
            audit_date=self._audit_reference_date(audit),
            leader_name=leader_name or "—",
            conclusion=conclusion,
        )

    @staticmethod
    def _leader_name(audit_id: int) -> str:
        for member in audit_commission_service.get_for_audit(audit_id):
            if member.record_type == COMMISSION_RECORD_LEADER:
                return str(member.display_name or "").strip()
        return ""

    @staticmethod
    def _audit_conclusion(audit) -> str:
        summary = audit_service.get_conclusion_summary(audit.id)
        parts = [audit.status or "—"]
        if summary["findings_open"]:
            parts.append(f"{summary['findings_open']} otevřených zjištění")
        if summary["tasks_active"]:
            parts.append(f"{summary['tasks_active']} aktivních úkolů")
        return " — ".join(parts)

    @staticmethod
    def _audit_reference_date(audit) -> date | None:
        return audit.audit_date or audit.finished_at or audit.started_at

    def _collect_open_findings(self, audits) -> list[WorkplaceFindingHistoryItem]:
        audit_numbers = {
            audit.id: str(audit.number or "").strip() or str(audit.id) for audit in audits
        }
        items: list[WorkplaceFindingHistoryItem] = []
        for audit in audits:
            for finding in finding_service.get_for_entity(ENTITY_AUDITY, audit.id):
                if finding.status == FINDING_STATUS_VYPORADANO:
                    continue
                items.append(
                    WorkplaceFindingHistoryItem(
                        finding_id=finding.id,
                        title=self._finding_title(finding),
                        severity_label=self._finding_severity_label(finding),
                        due_date=finding.due_date,
                        status_label=finding_status_label(finding.status),
                        audit_id=audit.id,
                        audit_number=audit_numbers[audit.id],
                    )
                )
        items.sort(
            key=lambda item: (
                item.due_date or date.max,
                item.finding_id,
            )
        )
        return items

    @staticmethod
    def _finding_title(finding) -> str:
        description = str(finding.description or "").strip()
        if description:
            return description.splitlines()[0][:120]
        if finding.source_control_point_label:
            return str(finding.source_control_point_label).strip()
        if finding.reference_label:
            return str(finding.reference_label).strip()
        return f"Zjištění #{finding.id}"

    @staticmethod
    def _finding_severity_label(finding) -> str:
        audit_label = AUDIT_FINDING_TYPE_LABELS.get(finding.finding_type)
        if audit_label:
            return audit_label
        return finding_type_label(finding.finding_type)

    def _collect_open_tasks(
        self,
        audits,
        findings: list[WorkplaceFindingHistoryItem],
    ) -> list[WorkplaceTaskHistoryItem]:
        seen_task_ids: set[int] = set()
        items: list[WorkplaceTaskHistoryItem] = []

        for audit in audits:
            for task in audit_service.get_tasks_for_audit(audit.id):
                if task.id in seen_task_ids:
                    continue
                if task.computed_status in {"Ukončeno", "Zrušeno"}:
                    continue
                seen_task_ids.add(task.id)
                items.append(self._task_item(task))

        for finding in findings:
            finding_row = finding_service.get_by_id(finding.finding_id)
            if finding_row is None or finding_row.task_id is None:
                continue
            task_id = finding_row.task_id
            if task_id in seen_task_ids:
                continue
            task = task_service.get_task_by_id(task_id)
            if task is None or task.computed_status in {"Ukončeno", "Zrušeno"}:
                continue
            seen_task_ids.add(task_id)
            items.append(self._task_item(task))

        items.sort(key=lambda item: (item.due_date or date.max, item.task_id))
        return items

    @staticmethod
    def _task_item(task) -> WorkplaceTaskHistoryItem:
        completed = task.computed_status == "Ukončeno"
        return WorkplaceTaskHistoryItem(
            task_id=task.id,
            title=task_description_table_text(task),
            responsible_person=task.responsible_person or "—",
            due_date=task.due_date,
            completion_label="Ano" if completed else "Ne",
        )

    def _build_process_history(
        self,
        workplace_id: int,
        audits,
    ) -> list[WorkplaceProcessHistoryItem]:
        last_by_process = self._last_audit_dates_from_control_results(audits)
        last_by_process.update(self._last_audit_dates_from_program(workplace_id))

        items: list[WorkplaceProcessHistoryItem] = []
        for process in audit_knowledge_service.get_processes():
            last_date = last_by_process.get(process.id)
            items.append(
                WorkplaceProcessHistoryItem(
                    process_id=process.id,
                    process_name=process.nazev,
                    last_audit_label=self._format_period_label(last_date),
                    last_audit_date=last_date,
                )
            )
        items.sort(key=lambda item: (item.last_audit_date is None, item.process_name.lower()))
        return items

    @staticmethod
    def _last_audit_dates_from_control_results(audits) -> dict[str, date]:
        last_by_process: dict[str, date] = {}
        for audit in audits:
            audit_date = AuditHistoryService._audit_reference_date(audit)
            if audit_date is None:
                continue
            for result in control_result_service.get_for_entity(ENTITY_AUDITY, audit.id):
                process_id = str(result.source_area_id or "").strip()
                if not process_id:
                    continue
                if result.result == CONTROL_RESULT_NEKONTROLOVANO:
                    continue
                current = last_by_process.get(process_id)
                if current is None or audit_date > current:
                    last_by_process[process_id] = audit_date
        return last_by_process

    def _last_audit_dates_from_program(self, workplace_id: int) -> dict[str, date]:
        last_by_process: dict[str, date] = {}
        for visit in self.program_repository.list_visits_by_workplace(workplace_id):
            if visit.status != AUDIT_PROGRAM_VISIT_STATUS_COMPLETED:
                continue
            visit_date = visit.planned_date
            if visit_date is None and visit.planned_month and visit.planned_year:
                visit_date = date(visit.planned_year, visit.planned_month, 1)
            if visit_date is None:
                continue
            for visit_process in self.program_repository.list_visit_processes(visit.id):
                if visit_process.status != AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED:
                    continue
                process_id = str(visit_process.process_id or "").strip()
                if not process_id:
                    continue
                current = last_by_process.get(process_id)
                if current is None or visit_date > current:
                    last_by_process[process_id] = visit_date
        return last_by_process

    @staticmethod
    def _format_period_label(value: date | None) -> str:
        if value is None:
            return "Nikdy"
        if 1 <= value.month <= 12:
            return f"{MONTH_NAMES_CAPITALIZED[value.month - 1]} {value.year}"
        return value.strftime("%d.%m.%Y")

    @staticmethod
    def _build_summary(
        last_audit: WorkplaceLastAuditSummary | None,
        findings: list[WorkplaceFindingHistoryItem],
        tasks: list[WorkplaceTaskHistoryItem],
        process_history: list[WorkplaceProcessHistoryItem],
    ) -> WorkplaceHistorySummary:
        audited_count = sum(1 for item in process_history if item.last_audit_date is not None)
        return WorkplaceHistorySummary(
            last_audit_date=last_audit.audit_date if last_audit is not None else None,
            open_findings_count=len(findings),
            open_tasks_count=len(tasks),
            audited_processes_count=audited_count,
            total_processes_count=len(process_history),
        )


audit_history_service = AuditHistoryService()
