"""Historie provozu pro záložku Úvod (AUDIT-INTRO-1 / AUDIT-INTRO-2).

Bez N+1: audity jedním dotazem, zjištění a úkoly hromadně.
Nevolá ensure_catalogs / get_knowledge_tree.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date, datetime

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
class WorkplacePreviousAuditItem:
    audit_id: int
    audit_number: str
    audit_date: date | None
    status: str
    audit_type: str
    program_name: str


@dataclass(frozen=True)
class WorkplaceFindingHistoryItem:
    finding_id: int
    title: str
    severity_label: str
    due_date: date | None
    status_label: str
    audit_id: int
    audit_number: str
    created_at: date | None = None
    resolved_at: date | None = None


@dataclass(frozen=True)
class WorkplaceTaskHistoryItem:
    task_id: int
    title: str
    responsible_person: str
    due_date: date | None
    status_label: str
    completed_date: date | None
    finding_title: str = ""
    audit_id: int | None = None
    audit_number: str = ""


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
    previous_audits_count: int = 0
    findings_total_count: int = 0
    tasks_total_count: int = 0


@dataclass(frozen=True)
class WorkplaceHistory:
    last_audit: WorkplaceLastAuditSummary | None
    previous_audits: tuple[WorkplacePreviousAuditItem, ...]
    findings: tuple[WorkplaceFindingHistoryItem, ...]
    tasks: tuple[WorkplaceTaskHistoryItem, ...]
    process_history: tuple[WorkplaceProcessHistoryItem, ...]
    summary: WorkplaceHistorySummary
    is_first_audit: bool = False


@dataclass(frozen=True)
class WorkplaceHistoryContinuityAggregate:
    """Souhrnné počty historie pro roční / závěrečnou zprávu (AUDIT-INTRO-2).

    Entity se sčítají podle ID pouze jednou (bez duplicit napříč provozy).
    Připraveno na budoucí rozšíření o provozní zjištění z externích auditů.
    """

    previous_audits_count: int
    findings_total_count: int
    findings_open_count: int
    findings_resolved_count: int
    tasks_total_count: int
    tasks_active_count: int
    tasks_completed_count: int
    tasks_canceled_count: int


_TASK_STATUS_COMPLETED = "Ukončeno"
_TASK_STATUS_CANCELED = "Zrušeno"


class AuditHistoryService:
    def __init__(self) -> None:
        self.audit_repository = AuditRepository()
        self.program_repository = AuditProgramRepository()

    def get_workplace_history(
        self,
        workplace_id: int | None,
        *,
        current_audit=None,
        exclude_audit_id: int | None = None,
        exclude_audit_ids: Collection[int] | None = None,
        program_id: int | None = None,
        include_process_history: bool = False,
    ) -> WorkplaceHistory:
        if workplace_id is None:
            return self._empty_history()

        current = current_audit
        if current is None and exclude_audit_id is not None:
            current = self.audit_repository.get_by_id(int(exclude_audit_id))

        excluded: set[int] = set()
        if exclude_audit_id is not None:
            excluded.add(int(exclude_audit_id))
        if exclude_audit_ids:
            excluded.update(int(item) for item in exclude_audit_ids)
        if current is not None and getattr(current, "id", None) is not None:
            excluded.add(int(current.id))

        as_of = self._history_as_of(current)
        if as_of is None:
            return self._empty_history()

        audits = self._previous_started_audits(
            self.audit_repository.list_for_workplace(workplace_id),
            as_of=as_of,
            excluded_ids=excluded,
        )
        if program_id is not None:
            audits = self._filter_audits_for_program(audits, program_id)

        return self._history_from_audits(
            audits,
            workplace_id=workplace_id,
            include_process_history=include_process_history,
        )

    def aggregate_continuity_for_audits(
        self,
        audits: Sequence,
    ) -> WorkplaceHistoryContinuityAggregate:
        """Agregace historie pro reportované audity — jedno volání na provoz, bez N+1.

        Aktuální audity ze vstupu (a jejich zjištění/úkoly) se do historie nezapočítávají.
        Stejná entita se napříč provozy započte jen jednou podle ID.
        """
        current_by_workplace: dict[int, list] = {}
        for audit in audits:
            workplace_id = getattr(audit, "workplace_id", None)
            audit_id = getattr(audit, "id", None)
            if workplace_id is None or audit_id is None:
                continue
            current_by_workplace.setdefault(int(workplace_id), []).append(audit)

        previous_audit_ids: set[int] = set()
        finding_ids: set[int] = set()
        open_finding_ids: set[int] = set()
        resolved_finding_ids: set[int] = set()
        task_ids: set[int] = set()
        active_task_ids: set[int] = set()
        completed_task_ids: set[int] = set()
        canceled_task_ids: set[int] = set()
        resolved_label = finding_status_label(FINDING_STATUS_VYPORADANO)

        visit_ids = [
            int(audit.program_visit_id)
            for group in current_by_workplace.values()
            for audit in group
            if getattr(audit, "started_at", None) is None
            and getattr(audit, "program_visit_id", None) is not None
        ]
        visits = self.program_repository.get_visits_by_ids(visit_ids)

        reported_ids = {
            int(audit.id)
            for group in current_by_workplace.values()
            for audit in group
            if getattr(audit, "id", None) is not None
        }

        for workplace_id, current_group in current_by_workplace.items():
            workplace_audits = self.audit_repository.list_for_workplace(workplace_id)
            selected: list = []
            seen: set[int] = set()
            for current in current_group:
                visit = None
                visit_id = getattr(current, "program_visit_id", None)
                if visit_id is not None:
                    visit = visits.get(int(visit_id))
                as_of = self._history_as_of(current, visit=visit)
                if as_of is None:
                    continue
                for previous in self._previous_started_audits(
                    workplace_audits,
                    as_of=as_of,
                    excluded_ids=reported_ids | {int(current.id)},
                ):
                    if previous.id in seen:
                        continue
                    seen.add(int(previous.id))
                    selected.append(previous)
            history = self._history_from_audits(selected)
            for item in history.previous_audits:
                previous_audit_ids.add(int(item.audit_id))
            for item in history.findings:
                finding_id = int(item.finding_id)
                finding_ids.add(finding_id)
                if item.status_label == resolved_label:
                    resolved_finding_ids.add(finding_id)
                else:
                    open_finding_ids.add(finding_id)
            for item in history.tasks:
                task_id = int(item.task_id)
                task_ids.add(task_id)
                if item.status_label == _TASK_STATUS_COMPLETED:
                    completed_task_ids.add(task_id)
                elif item.status_label == _TASK_STATUS_CANCELED:
                    canceled_task_ids.add(task_id)
                else:
                    active_task_ids.add(task_id)

        return WorkplaceHistoryContinuityAggregate(
            previous_audits_count=len(previous_audit_ids),
            findings_total_count=len(finding_ids),
            findings_open_count=len(open_finding_ids),
            findings_resolved_count=len(resolved_finding_ids),
            tasks_total_count=len(task_ids),
            tasks_active_count=len(active_task_ids),
            tasks_completed_count=len(completed_task_ids),
            tasks_canceled_count=len(canceled_task_ids),
        )

    def _history_from_audits(
        self,
        audits,
        *,
        workplace_id: int | None = None,
        include_process_history: bool = False,
    ) -> WorkplaceHistory:
        is_first = len(audits) == 0
        last_audit = self._build_last_audit_summary(audits[0]) if audits else None
        previous_audits = self._build_previous_audits(audits)
        raw_findings = finding_service.get_for_entities(
            ENTITY_AUDITY,
            [audit.id for audit in audits],
        )
        findings = self._map_findings(audits, raw_findings)
        tasks = self._collect_tasks(raw_findings, findings)
        process_history: list[WorkplaceProcessHistoryItem] = []
        if include_process_history and workplace_id is not None:
            process_history = self._build_process_history(workplace_id, audits)
        summary = self._build_summary(
            last_audit,
            findings,
            tasks,
            process_history,
            previous_audits_count=len(previous_audits),
        )
        return WorkplaceHistory(
            last_audit=last_audit,
            previous_audits=tuple(previous_audits),
            findings=tuple(findings),
            tasks=tuple(tasks),
            process_history=tuple(process_history),
            summary=summary,
            is_first_audit=is_first,
        )

    def _history_as_of(self, audit, visit=None) -> date | None:
        """Časový bod aktuálního auditu: started_at, jinak plán návštěvy programu."""
        if audit is None:
            return None
        started = self._as_date(getattr(audit, "started_at", None))
        if started is not None:
            return started
        if visit is None:
            visit_id = getattr(audit, "program_visit_id", None)
            if visit_id is not None:
                visit = self.program_repository.get_visit(int(visit_id))
        if visit is None:
            return None
        planned = self._as_date(getattr(visit, "planned_date", None))
        if planned is not None:
            return planned
        year = getattr(visit, "planned_year", None)
        month = getattr(visit, "planned_month", None)
        if year and month:
            return date(int(year), int(month), 1)
        return None

    @staticmethod
    def _as_date(value) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return None

    @staticmethod
    def _previous_started_audits(audits, *, as_of: date, excluded_ids: set[int]):
        previous = [
            audit
            for audit in audits
            if int(audit.id) not in excluded_ids
            and getattr(audit, "started_at", None) is not None
            and audit.started_at < as_of
        ]
        previous.sort(
            key=lambda item: (item.started_at, item.id),
            reverse=True,
        )
        return previous

    def _empty_history(self) -> WorkplaceHistory:
        summary = WorkplaceHistorySummary(
            last_audit_date=None,
            open_findings_count=0,
            open_tasks_count=0,
            audited_processes_count=0,
            total_processes_count=0,
            previous_audits_count=0,
            findings_total_count=0,
            tasks_total_count=0,
        )
        return WorkplaceHistory(
            last_audit=None,
            previous_audits=(),
            findings=(),
            tasks=(),
            process_history=(),
            summary=summary,
            is_first_audit=True,
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

    def _build_previous_audits(self, audits) -> list[WorkplacePreviousAuditItem]:
        program_ids = [
            int(audit.program_id)
            for audit in audits
            if getattr(audit, "program_id", None) is not None
        ]
        programs = self.program_repository.get_programs_by_ids(program_ids)
        items: list[WorkplacePreviousAuditItem] = []
        for audit in audits:
            program_name = "—"
            if audit.program_id is not None:
                program = programs.get(int(audit.program_id))
                if program is not None:
                    program_name = str(program.name or "").strip() or "—"
            items.append(
                WorkplacePreviousAuditItem(
                    audit_id=audit.id,
                    audit_number=str(audit.number or "").strip() or str(audit.id),
                    audit_date=self._audit_reference_date(audit),
                    status=str(audit.status or "—"),
                    audit_type=str(audit.audit_type or "—"),
                    program_name=program_name,
                )
            )
        return items

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

    def _map_findings(self, audits, raw_findings) -> list[WorkplaceFindingHistoryItem]:
        if not audits:
            return []
        audit_numbers = {
            audit.id: str(audit.number or "").strip() or str(audit.id) for audit in audits
        }
        items: list[WorkplaceFindingHistoryItem] = []
        for finding in raw_findings:
            created = finding.created_at
            created_date = created.date() if isinstance(created, datetime) else created
            items.append(
                WorkplaceFindingHistoryItem(
                    finding_id=finding.id,
                    title=self._finding_title(finding),
                    severity_label=self._finding_severity_label(finding),
                    due_date=finding.due_date,
                    status_label=finding_status_label(finding.status),
                    audit_id=finding.entity_id,
                    audit_number=audit_numbers.get(
                        finding.entity_id, str(finding.entity_id)
                    ),
                    created_at=created_date,
                    resolved_at=finding.resolved_at,
                )
            )
        items.sort(
            key=lambda item: (
                item.created_at or date.min,
                item.finding_id,
            ),
            reverse=True,
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

    def _filter_audits_for_program(self, audits, program_id: int) -> list:
        return [audit for audit in audits if audit.program_id == program_id]

    def _collect_tasks(
        self,
        raw_findings,
        findings: list[WorkplaceFindingHistoryItem],
    ) -> list[WorkplaceTaskHistoryItem]:
        finding_item_by_id = {item.finding_id: item for item in findings}
        finding_by_task: dict[int, WorkplaceFindingHistoryItem] = {}
        task_ids: list[int] = []
        for raw in raw_findings:
            if raw.task_id is None:
                continue
            task_id = int(raw.task_id)
            task_ids.append(task_id)
            item = finding_item_by_id.get(raw.id)
            if item is not None:
                finding_by_task[task_id] = item

        unique_ids = list(dict.fromkeys(task_ids))
        tasks = task_service.get_tasks_by_ids(unique_ids)
        items: list[WorkplaceTaskHistoryItem] = []
        for task in tasks:
            linked = finding_by_task.get(task.id)
            items.append(
                WorkplaceTaskHistoryItem(
                    task_id=task.id,
                    title=task_description_table_text(task),
                    responsible_person=task.responsible_person or "—",
                    due_date=task.due_date,
                    status_label=task.computed_status,
                    completed_date=task.completed_date,
                    finding_title=linked.title if linked else "—",
                    audit_id=linked.audit_id if linked else None,
                    audit_number=linked.audit_number if linked else "—",
                )
            )
        items.sort(
            key=lambda item: (
                item.status_label in {"Ukončeno", "Zrušeno"},
                item.due_date or date.max,
                item.task_id,
            )
        )
        return items

    def _build_process_history(
        self,
        workplace_id: int,
        audits,
    ) -> list[WorkplaceProcessHistoryItem]:
        # Volitelné — jen při include_process_history. Bez ensure_catalogs.
        from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service

        last_by_process = self._last_audit_dates_from_control_results(audits)
        last_by_process.update(self._last_audit_dates_from_program(workplace_id))

        items: list[WorkplaceProcessHistoryItem] = []
        for process in audit_knowledge_service.get_processes(ensure=False):
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
        *,
        previous_audits_count: int,
    ) -> WorkplaceHistorySummary:
        audited_count = sum(1 for item in process_history if item.last_audit_date is not None)
        resolved_label = finding_status_label(FINDING_STATUS_VYPORADANO)
        open_findings = sum(1 for item in findings if item.status_label != resolved_label)
        return WorkplaceHistorySummary(
            last_audit_date=last_audit.audit_date if last_audit is not None else None,
            open_findings_count=open_findings,
            open_tasks_count=sum(
                1 for item in tasks if item.status_label not in {"Ukončeno", "Zrušeno"}
            ),
            audited_processes_count=audited_count,
            total_processes_count=len(process_history),
            previous_audits_count=previous_audits_count,
            findings_total_count=len(findings),
            tasks_total_count=len(tasks),
        )


audit_history_service = AuditHistoryService()
