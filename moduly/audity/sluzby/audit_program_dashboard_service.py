from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.shared.constants import (
    ENTITY_AUDITY,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
)
from core.shared.finding_display import finding_status_label
from core.shared.sluzby.finding_service import finding_service
from moduly.audity.constants import (
    AUDIT_FINDING_TYPE_LABELS,
    AUDIT_FINDING_TYPE_NESHODA,
    audit_finding_type_label,
)
from moduly.audity.repository.audit_program_repository import AuditProgramRepository
from moduly.audity.repository.audit_repository import AuditRepository
from moduly.audity.sluzby.audit_service import audit_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.task_display import task_description_table_text


@dataclass(frozen=True)
class ProgramFindingItem:
    finding_id: int
    workplace_name: str
    audit_id: int
    audit_number: str
    process_name: str
    title: str
    severity_label: str
    due_date: date | None
    status_label: str
    responsible_person: str
    is_open: bool
    is_overdue: bool
    is_severe: bool
    status: str = ""
    finding_type: str = ""


@dataclass(frozen=True)
class ProgramTaskItem:
    task_id: int
    workplace_name: str
    audit_id: int
    audit_number: str
    title: str
    responsible_person: str
    due_date: date | None
    completion_label: str
    status_label: str
    is_open: bool
    is_overdue: bool


@dataclass(frozen=True)
class ProgramDashboardSummary:
    findings_total: int
    findings_open: int
    findings_overdue: int
    findings_critical: int
    tasks_total: int
    tasks_open: int
    tasks_overdue: int


class AuditProgramDashboardService:
    def __init__(self) -> None:
        self.program_repository = AuditProgramRepository()
        self.audit_repository = AuditRepository()

    def get_program_findings(self, program_id: int) -> tuple[ProgramFindingItem, ...]:
        return tuple(self._collect_findings(program_id))

    def get_program_tasks(self, program_id: int) -> tuple[ProgramTaskItem, ...]:
        return tuple(self._collect_tasks(program_id))

    def get_program_summary(self, program_id: int) -> ProgramDashboardSummary:
        findings = self._collect_findings(program_id)
        tasks = self._collect_tasks(program_id)
        return ProgramDashboardSummary(
            findings_total=len(findings),
            findings_open=sum(1 for item in findings if item.is_open),
            findings_overdue=sum(1 for item in findings if item.is_overdue),
            findings_critical=sum(
                1 for item in findings if item.is_open and item.is_severe
            ),
            tasks_total=len(tasks),
            tasks_open=sum(1 for item in tasks if item.is_open),
            tasks_overdue=sum(1 for item in tasks if item.is_overdue),
        )

    def _collect_findings(self, program_id: int) -> list[ProgramFindingItem]:
        if self.program_repository.get_program(program_id) is None:
            return []

        today = date.today()
        items: list[ProgramFindingItem] = []
        for audit in self._program_audits(program_id):
            audit_number = str(audit.number or "").strip() or str(audit.id)
            workplace_name = str(audit.workplace_name or "").strip() or "—"
            for finding in finding_service.get_for_entity(ENTITY_AUDITY, audit.id):
                is_open = finding.status in (
                    FINDING_STATUS_OTEVRENE,
                    FINDING_STATUS_V_PROCESU,
                )
                is_overdue = (
                    is_open
                    and finding.due_date is not None
                    and finding.due_date < today
                )
                is_severe = finding.finding_type == AUDIT_FINDING_TYPE_NESHODA
                items.append(
                    ProgramFindingItem(
                        finding_id=finding.id,
                        workplace_name=workplace_name,
                        audit_id=audit.id,
                        audit_number=audit_number,
                        process_name=str(finding.source_area_label or "").strip() or "—",
                        title=self._finding_title(finding),
                        severity_label=self._finding_severity_label(finding),
                        due_date=finding.due_date,
                        status_label=finding_status_label(finding.status),
                        responsible_person=str(finding.responsible_person_name or "").strip()
                        or "—",
                        is_open=is_open,
                        is_overdue=is_overdue,
                        is_severe=is_severe,
                        status=finding.status,
                        finding_type=finding.finding_type,
                    )
                )
        items.sort(
            key=lambda item: (
                not item.is_open,
                item.due_date or date.max,
                item.finding_id,
            )
        )
        return items

    def _collect_tasks(self, program_id: int) -> list[ProgramTaskItem]:
        if self.program_repository.get_program(program_id) is None:
            return []

        today = date.today()
        items: list[ProgramTaskItem] = []
        seen_task_ids: set[int] = set()

        for audit in self._program_audits(program_id):
            audit_number = str(audit.number or "").strip() or str(audit.id)
            workplace_name = str(audit.workplace_name or "").strip() or "—"
            for task in audit_service.get_tasks_for_audit(audit.id):
                if task.id in seen_task_ids:
                    continue
                seen_task_ids.add(task.id)
                is_open = task.computed_status not in {"Ukončeno", "Zrušeno"}
                is_overdue = (
                    is_open
                    and task.due_date is not None
                    and task.due_date < today
                )
                items.append(
                    ProgramTaskItem(
                        task_id=task.id,
                        workplace_name=workplace_name,
                        audit_id=audit.id,
                        audit_number=audit_number,
                        title=task_description_table_text(task),
                        responsible_person=task.responsible_person or "—",
                        due_date=task.due_date,
                        completion_label="Ano"
                        if task.computed_status == "Ukončeno"
                        else "Ne",
                        status_label=task.computed_status,
                        is_open=is_open,
                        is_overdue=is_overdue,
                    )
                )

        items.sort(
            key=lambda item: (
                not item.is_open,
                item.due_date or date.max,
                item.task_id,
            )
        )
        return items

    def _program_audits(self, program_id: int):
        audits = self.audit_repository.list_for_program(program_id)
        audits_by_id = {audit.id: audit for audit in audits}
        for visit in self.program_repository.list_visits(program_id):
            if visit.audit_id is None or visit.audit_id in audits_by_id:
                continue
            audit = self.audit_repository.get_by_id(visit.audit_id)
            if audit is not None:
                audits_by_id[audit.id] = audit
        return list(audits_by_id.values())

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
        label = audit_finding_type_label(finding.finding_type)
        if label != finding.finding_type:
            return label
        return AUDIT_FINDING_TYPE_LABELS.get(finding.finding_type, finding.finding_type)


audit_program_dashboard_service = AuditProgramDashboardService()
