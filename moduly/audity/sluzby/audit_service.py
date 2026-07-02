from datetime import date, datetime
from dataclasses import dataclass

from core.shared.constants import (
    ENTITY_AUDITY,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
)
from core.shared.modely.finding import Finding
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from moduly.audity.constants import (
    AUDIT_SPIS_STATUSES,
    AUDIT_STATUS_DOKONCENO,
    AUDIT_STATUS_PLANOVANO,
    AUDIT_STATUS_PROBIHA,
    AUDIT_TYPES,
    DEFAULT_AUDIT_TYPE,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.repository.audit_repository import AuditRepository
from moduly.audity.sluzby.audit_commission_service import audit_commission_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.ukoly.modely.task import Task
from moduly.ukoly.sluzby.task_service import task_service


@dataclass(frozen=True)
class CompletionBlockers:
    open_findings: list[Finding]
    active_tasks: list[Task]

    def has_blockers(self) -> bool:
        return bool(self.open_findings or self.active_tasks)


class AuditService:
    def __init__(self):
        self.repository = AuditRepository()

    def get_all(self) -> list[Audit]:
        return self.repository.get_all()

    def get_by_id(self, audit_id: int) -> Audit | None:
        return self.repository.get_by_id(audit_id)

    def create_audit(self, **fields) -> Audit:
        data = self._validated_fields(fields)
        audit = Audit(**data)
        saved = self.repository.add(audit)
        saved.number = self._make_number(saved.id, saved.year)
        return self.repository.update(saved)

    def update_audit(self, audit_id: int, **fields) -> Audit | None:
        audit = self.repository.get_by_id(audit_id)
        if audit is None:
            return None

        was_finished = audit.finished_at is not None

        merged = {
            "year": audit.year,
            "planned_month": audit.planned_month,
            "audit_date": audit.audit_date,
            "started_at": audit.started_at,
            "finished_at": audit.finished_at,
            "audit_type": audit.audit_type,
            "workplace_id": audit.workplace_id,
            "workplace_name": audit.workplace_name,
            "title": audit.title,
            "program_id": audit.program_id,
            "program_visit_id": audit.program_visit_id,
        }
        merged.update(fields)
        data = self._validated_fields(merged)
        for key, value in data.items():
            setattr(audit, key, value)
        audit.updated_at = datetime.now()
        updated = self.repository.update(audit)

        if not was_finished and updated.finished_at is not None:
            from moduly.audity.sluzby.audit_program_service import audit_program_service

            audit_program_service.sync_on_audit_completed(
                updated.id,
                finished_at=updated.finished_at,
            )

        return updated

    def delete_audit(self, audit_id: int) -> bool:
        finding_service.delete_for_entity(ENTITY_AUDITY, audit_id)
        control_result_service.delete_for_entity(ENTITY_AUDITY, audit_id)
        audit_commission_service.delete_for_audit(audit_id)
        return self.repository.delete(audit_id)

    def resolve_workplace_name(self, workplace_id: int | None) -> str:
        if not workplace_id:
            return ""

        workplace = settings_service.get_workplace_by_id(workplace_id)
        return workplace.name if workplace else ""

    def resolve_workplace_id_by_name(self, workplace_name: str) -> int | None:
        name = str(workplace_name or "").strip()
        if not name:
            return None

        for workplace in settings_service.get_workplaces(include_inactive=True):
            if workplace.name == name:
                return workplace.id
        return None

    def finding_for_control_point(
        self,
        audit_id: int,
        *,
        process_label: str,
        criterion_label: str,
        question_id: str,
    ) -> Finding | None:
        if not question_id:
            return None

        for finding in finding_service.get_for_entity(ENTITY_AUDITY, audit_id):
            if self._matches_control_point(
                finding,
                process_label=process_label,
                criterion_label=criterion_label,
                question_id=question_id,
            ):
                return finding
        return None

    def get_tasks_for_audit(self, audit_id: int) -> list[Task]:
        tasks: list[Task] = []
        seen_task_ids: set[int] = set()

        for finding in finding_service.get_for_entity(ENTITY_AUDITY, audit_id):
            task_id = finding.task_id
            if task_id is None or task_id in seen_task_ids:
                continue

            task = task_service.get_task_by_id(task_id)
            if task is None:
                continue

            tasks.append(task)
            seen_task_ids.add(task_id)

        return sorted(tasks, key=lambda item: (item.due_date or date.max, item.id))

    def get_completion_blockers(self, audit_id: int) -> CompletionBlockers:
        open_findings = [
            finding
            for finding in finding_service.get_for_entity(ENTITY_AUDITY, audit_id)
            if finding.status != FINDING_STATUS_VYPORADANO
        ]
        active_tasks = [
            task
            for task in self.get_tasks_for_audit(audit_id)
            if task.computed_status not in {"Ukončeno", "Zrušeno"}
        ]
        return CompletionBlockers(open_findings=open_findings, active_tasks=active_tasks)

    def get_conclusion_summary(self, audit_id: int) -> dict[str, int]:
        findings = finding_service.get_for_entity(ENTITY_AUDITY, audit_id)
        blockers = self.get_completion_blockers(audit_id)
        tasks = self.get_tasks_for_audit(audit_id)
        return {
            "findings_total": len(findings),
            "findings_open": len(blockers.open_findings),
            "tasks_total": len(tasks),
            "tasks_active": len(blockers.active_tasks),
        }

    def open_finding_for_control_point(
        self,
        audit_id: int,
        *,
        process_label: str,
        criterion_label: str,
        question_id: str,
    ) -> Finding | None:
        finding = self.finding_for_control_point(
            audit_id,
            process_label=process_label,
            criterion_label=criterion_label,
            question_id=question_id,
        )
        if finding is None:
            return None
        from core.shared.constants import FINDING_STATUS_OTEVRENE, FINDING_STATUS_V_PROCESU

        if finding.status not in (FINDING_STATUS_OTEVRENE, FINDING_STATUS_V_PROCESU):
            return None
        return finding

    @staticmethod
    def _matches_control_point(
        finding: Finding,
        *,
        process_label: str,
        criterion_label: str,
        question_id: str,
    ) -> bool:
        return (
            str(finding.source_control_point_id or "").strip() == question_id
            and str(finding.source_area_label or "").strip() == process_label.strip()
            and str(finding.source_section_label or "").strip() == criterion_label.strip()
        )

    @staticmethod
    def derive_status(
        started_at: date | None,
        finished_at: date | None,
    ) -> str:
        if finished_at is not None:
            return AUDIT_STATUS_DOKONCENO
        if started_at is not None:
            return AUDIT_STATUS_PROBIHA
        return AUDIT_STATUS_PLANOVANO

    def _validated_fields(self, fields: dict) -> dict:
        data = dict(fields)

        audit_type = data.get("audit_type", DEFAULT_AUDIT_TYPE)
        if audit_type not in AUDIT_TYPES:
            raise ValueError(f"Neplatný typ auditu: {audit_type}")

        if data.get("year") is None:
            data["year"] = date.today().year

        workplace_id = data.get("workplace_id")
        if workplace_id is not None:
            data["workplace_id"] = int(workplace_id)
        else:
            data["workplace_id"] = None

        program_id = data.get("program_id")
        data["program_id"] = int(program_id) if program_id is not None else None

        program_visit_id = data.get("program_visit_id")
        data["program_visit_id"] = (
            int(program_visit_id) if program_visit_id is not None else None
        )

        data["workplace_name"] = str(data.get("workplace_name") or "").strip()
        data["title"] = str(data.get("title") or "").strip()

        started_at = data.get("started_at")
        finished_at = data.get("finished_at")
        status = self.derive_status(started_at, finished_at)
        if status not in AUDIT_SPIS_STATUSES:
            raise ValueError(f"Neplatný stav auditu: {status}")

        return {
            "year": data.get("year"),
            "planned_month": data.get("planned_month"),
            "audit_date": data.get("audit_date"),
            "started_at": started_at,
            "finished_at": finished_at,
            "status": status,
            "audit_type": audit_type,
            "workplace_id": data.get("workplace_id"),
            "workplace_name": data["workplace_name"],
            "title": data["title"],
            "program_id": data.get("program_id"),
            "program_visit_id": data.get("program_visit_id"),
        }

    @staticmethod
    def _make_number(audit_id: int, year: int | None) -> str:
        number_year = year or date.today().year
        return f"{audit_id}/{number_year}"


audit_service = AuditService()
