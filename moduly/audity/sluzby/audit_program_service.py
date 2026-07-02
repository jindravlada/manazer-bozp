import json
from dataclasses import dataclass
from datetime import date, datetime

from moduly.audity.constants import (
    AUDIT_PROGRAM_MANUAL_DISTRIBUTE_BLOCKED,
    AUDIT_PROGRAM_MANUAL_GENERATE_BLOCKED,
    AUDIT_PROGRAM_STATUS_APPROVED,
    AUDIT_PROGRAM_STATUS_RUNNING,
    AUDIT_PROGRAM_STATUSES,
    AUDIT_PROGRAM_VISIT_HAS_AUDIT,
    AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED,
    AUDIT_PROGRAM_VISIT_PROCESS_STATUSES,
    AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_STATUS_SKIPPED,
    AUDIT_PROGRAM_VISIT_STATUSES,
    DEFAULT_AUDIT_PROGRAM_STANDARDS,
    DEFAULT_AUDIT_PROGRAM_STATUS,
    DEFAULT_AUDIT_PROGRAM_VISIT_PROCESS_STATUS,
    DEFAULT_AUDIT_PROGRAM_VISIT_STATUS,
    MONTH_NAMES_CAPITALIZED,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_program import (
    AuditProgram,
    AuditProgramVisit,
    AuditProgramVisitProcess,
    AuditProgramWorkplace,
)
from moduly.audity.repository.audit_program_repository import AuditProgramRepository
from moduly.audity.sluzby.audit_knowledge_service import (
    AuditProcessDefinition,
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_program_planning_config_service import (
    WorkplacePlanningConfig,
    audit_program_planning_config_service,
)
from moduly.nastaveni.constants.workplace_audit_constants import (
    DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS,
)
from moduly.nastaveni.sluzby.workplace_audit_planning import (
    iter_visit_month_anchors,
    parse_preferred_months_json,
    plan_visit_months,
)
from moduly.audity.sluzby.audit_program_visit_formatting import (
    format_planned_term,
    visit_sort_key,
)


@dataclass(frozen=True)
class AuditVisitContext:
    program_id: int
    visit_id: int
    program_name: str
    planned_process_ids: tuple[str, ...]
    standards: tuple[str, ...]


@dataclass(frozen=True)
class AuditProgramOverview:
    program: AuditProgram
    workplaces: list[AuditProgramWorkplace]
    visits: list[AuditProgramVisit]
    visit_processes: list[AuditProgramVisitProcess]


@dataclass(frozen=True)
class AuditProgramWorkplaceCoverage:
    workplace_id: int | None
    workplace_name: str
    missing_process_ids: tuple[str, ...]


@dataclass(frozen=True)
class AuditProgramCoverage:
    workplace_count: int
    visit_count: int
    completed_visit_count: int
    planned_process_count: int
    completed_process_count: int
    completion_percent: float
    missing_by_workplace: tuple[AuditProgramWorkplaceCoverage, ...]


@dataclass(frozen=True)
class PlannedVisitOverviewRow:
    visit_id: int
    planned_date: date | None
    planned_year: int | None
    planned_month: int | None
    sort_date: date | None
    workplace_name: str
    process_names: tuple[str, ...]
    status: str
    audit_id: int | None
    audit_number: str | None


@dataclass(frozen=True)
class AuditProgramBannerInfo:
    has_program: bool
    program_id: int | None
    program_name: str
    period_label: str
    completion_percent: float | None
    nearest_visit_term: str | None
    nearest_visit_workplace: str | None


@dataclass(frozen=True)
class AuditProgramGenerationResult:
    created_visits: tuple[AuditProgramVisit, ...]
    skipped_existing: int


@dataclass(frozen=True)
class AuditProgramDistributionResult:
    created_processes: tuple[AuditProgramVisitProcess, ...]
    skipped_existing: int


class AuditProgramService:
    def __init__(self) -> None:
        self.repository = AuditProgramRepository()

    def create_program(self, **fields) -> AuditProgram:
        data = self._validated_program_fields(fields)
        program = AuditProgram(**data)
        saved = self.repository.add_program(program)
        saved.number = self._make_number(saved.id)
        return self.repository.update_program(saved)

    def list_programs(self) -> list[AuditProgram]:
        return self.repository.list_programs()

    def get_active_program(self) -> AuditProgram | None:
        programs = self.list_programs()
        if not programs:
            return None

        for status in (AUDIT_PROGRAM_STATUS_RUNNING, AUDIT_PROGRAM_STATUS_APPROVED):
            candidates = [program for program in programs if program.status == status]
            if candidates:
                return self._newest_program(candidates)
        return self._newest_program(programs)

    def get_banner_info(self) -> AuditProgramBannerInfo:
        program = self.get_active_program()
        if program is None:
            return AuditProgramBannerInfo(
                has_program=False,
                program_id=None,
                program_name="",
                period_label="",
                completion_percent=None,
                nearest_visit_term=None,
                nearest_visit_workplace=None,
            )

        coverage = self.get_program_coverage(program.id)
        completion = coverage.completion_percent if coverage is not None else None
        nearest_visit = self.get_nearest_unstarted_visit(program.id)
        nearest_term = None
        nearest_workplace = None
        if nearest_visit is not None:
            nearest_term = format_planned_term(
                planned_date=nearest_visit.planned_date,
                planned_year=nearest_visit.planned_year,
                planned_month=nearest_visit.planned_month,
            )
            nearest_workplace = self._resolve_visit_workplace_name(program.id, nearest_visit)

        return AuditProgramBannerInfo(
            has_program=True,
            program_id=program.id,
            program_name=program.name.strip() or program.number.strip(),
            period_label=self._format_program_period(program.date_from, program.date_to),
            completion_percent=completion,
            nearest_visit_term=nearest_term,
            nearest_visit_workplace=nearest_workplace or None,
        )

    def get_nearest_unstarted_visit(self, program_id: int) -> AuditProgramVisit | None:
        visits = [
            visit
            for visit in self.repository.list_visits(program_id)
            if visit.status != AUDIT_PROGRAM_VISIT_STATUS_SKIPPED
            and visit.audit_id is None
        ]
        if not visits:
            return None

        today = date.today()
        dated_visits = [
            (self._visit_effective_date(visit), visit)
            for visit in visits
            if self._visit_effective_date(visit) is not None
        ]
        if not dated_visits:
            return sorted(visits, key=visit_sort_key)[0]

        dated_visits.sort(key=lambda item: (item[0], item[1].id))
        upcoming = [visit for effective, visit in dated_visits if effective >= today]
        if upcoming:
            return upcoming[0]

        return dated_visits[-1][1]

    @staticmethod
    def _newest_program(programs: list[AuditProgram]) -> AuditProgram:
        return max(
            programs,
            key=lambda program: (
                program.date_from or date.min,
                program.created_at or datetime.min,
                program.id,
            ),
        )

    @staticmethod
    def _visit_effective_date(visit: AuditProgramVisit) -> date | None:
        if visit.planned_date is not None:
            return visit.planned_date
        if visit.planned_year and visit.planned_month:
            return date(visit.planned_year, visit.planned_month, 1)
        return None

    @staticmethod
    def _format_program_period(date_from: date | None, date_to: date | None) -> str:
        if date_from is None or date_to is None:
            return "—"
        return (
            f"{date_from.day}. {date_from.month}. {date_from.year} – "
            f"{date_to.day}. {date_to.month}. {date_to.year}"
        )

    def get_program(self, program_id: int) -> AuditProgram | None:
        return self.repository.get_program(program_id)

    def update_program(self, program_id: int, **fields) -> AuditProgram:
        program = self.repository.get_program(program_id)
        if program is None:
            raise ValueError(f"Program auditů {program_id} neexistuje.")

        merged = {
            "number": program.number,
            "name": program.name,
            "date_from": program.date_from,
            "date_to": program.date_to,
            "status": program.status,
            "standards": program.standards_json,
            "description": program.description,
            "note": program.note,
            "created_at": program.created_at,
            "approved_at": program.approved_at,
            "closed_at": program.closed_at,
            "manual_planning": program.manual_planning,
        }
        merged.update(fields)
        data = self._validated_program_fields(merged)
        for key, value in data.items():
            if key == "created_at":
                continue
            setattr(program, key, value)
        return self.repository.update_program(program)

    def sync_workplaces_from_settings(self, program_id: int) -> int:
        if self.repository.get_program(program_id) is None:
            raise ValueError(f"Program auditů {program_id} neexistuje.")

        from moduly.nastaveni.sluzby.settings_service import settings_service

        existing_ids = {
            workplace.workplace_id
            for workplace in self.repository.list_workplaces(program_id)
        }
        created = 0
        for workplace in settings_service.get_workplaces():
            if not workplace.audit_enabled:
                continue
            if workplace.id in existing_ids:
                continue
            self.add_workplace(
                program_id,
                workplace_id=workplace.id,
                workplace_name=workplace.name,
                audit_interval_months=workplace.audit_interval_months,
                preferred_months_json=workplace.preferred_months_json,
                active=True,
            )
            created += 1
        return created

    def add_workplace(self, program_id: int, **fields) -> AuditProgramWorkplace:
        if self.repository.get_program(program_id) is None:
            raise ValueError(f"Program auditů {program_id} neexistuje.")

        data = self._validated_workplace_fields(fields)
        workplace = AuditProgramWorkplace(program_id=program_id, **data)
        return self.repository.add_workplace(workplace)

    def add_visit(self, program_id: int, **fields) -> AuditProgramVisit:
        if self.repository.get_program(program_id) is None:
            raise ValueError(f"Program auditů {program_id} neexistuje.")

        data = self._validated_visit_fields(fields)
        visit = AuditProgramVisit(program_id=program_id, **data)
        return self.repository.add_visit(visit)

    def add_visit_process(self, visit_id: int, **fields) -> AuditProgramVisitProcess:
        visit = self.repository.get_visit(visit_id)
        if visit is None:
            raise ValueError(f"Návštěva {visit_id} neexistuje.")

        data = self._validated_visit_process_fields(fields)
        visit_process = AuditProgramVisitProcess(visit_id=visit_id, **data)
        return self.repository.add_visit_process(visit_process)

    def create_manual_visit(
        self,
        program_id: int,
        *,
        workplace_id: int | None,
        planned_year: int,
        planned_month: int,
        planned_date: date | None = None,
        note: str = "",
    ) -> AuditProgramVisit:
        visit = self.add_visit(
            program_id,
            workplace_id=workplace_id,
            planned_year=planned_year,
            planned_month=planned_month,
            planned_date=planned_date,
            note=note,
        )
        self._mark_manual_planning(program_id)
        return visit

    def update_visit_plan(
        self,
        visit_id: int,
        *,
        planned_year: int,
        planned_month: int,
        planned_date: date | None = None,
        note: str | None = None,
    ) -> AuditProgramVisit:
        visit = self.repository.get_visit(visit_id)
        if visit is None:
            raise ValueError(f"Návštěva {visit_id} neexistuje.")
        if visit.status == AUDIT_PROGRAM_VISIT_STATUS_SKIPPED:
            raise ValueError("Zrušenou návštěvu nelze upravovat.")

        visit.planned_year = planned_year
        visit.planned_month = planned_month
        visit.planned_date = planned_date
        if note is not None:
            visit.note = note.strip()
        saved = self.repository.update_visit(visit)
        self._mark_manual_planning(visit.program_id)
        return saved

    def skip_visit(self, visit_id: int) -> AuditProgramVisit:
        visit = self.repository.get_visit(visit_id)
        if visit is None:
            raise ValueError(f"Návštěva {visit_id} neexistuje.")

        visit.status = AUDIT_PROGRAM_VISIT_STATUS_SKIPPED
        saved = self.repository.update_visit(visit)
        self._mark_manual_planning(visit.program_id)
        return saved

    def move_visit_process(
        self,
        visit_process_id: int,
        target_visit_id: int,
    ) -> AuditProgramVisitProcess:
        visit_process = self.repository.get_visit_process(visit_process_id)
        if visit_process is None:
            raise ValueError(f"Plánovaný proces {visit_process_id} neexistuje.")

        source_visit = self.repository.get_visit(visit_process.visit_id)
        target_visit = self.repository.get_visit(target_visit_id)
        if source_visit is None or target_visit is None:
            raise ValueError("Návštěva neexistuje.")
        if source_visit.program_id != target_visit.program_id:
            raise ValueError("Návštěvy musí patřit do stejného programu.")
        if source_visit.workplace_id != target_visit.workplace_id:
            raise ValueError("Proces lze přesunout pouze mezi návštěvami stejného pracoviště.")
        if target_visit.status == AUDIT_PROGRAM_VISIT_STATUS_SKIPPED:
            raise ValueError("Proces nelze přesunout do zrušené návštěvy.")

        for existing in self.repository.list_visit_processes(target_visit_id):
            if (
                existing.id != visit_process_id
                and existing.process_id == visit_process.process_id
            ):
                raise ValueError("Řídicí proces je v cílové návštěvě už naplánován.")

        visit_process.visit_id = target_visit_id
        saved = self.repository.update_visit_process(visit_process)
        self._mark_manual_planning(source_visit.program_id)
        return saved

    def list_workplace_visits(
        self,
        program_id: int,
        workplace_id: int | None,
        *,
        include_skipped: bool = True,
    ) -> list[AuditProgramVisit]:
        visits = [
            visit
            for visit in self.repository.list_visits(program_id)
            if visit.workplace_id == workplace_id
        ]
        if not include_skipped:
            visits = [
                visit
                for visit in visits
                if visit.status != AUDIT_PROGRAM_VISIT_STATUS_SKIPPED
            ]
        visits.sort(
            key=lambda item: (
                item.planned_year or 0,
                item.planned_month or 0,
                item.id,
            )
        )
        return visits

    def get_visit_by_audit_id(self, audit_id: int) -> AuditProgramVisit | None:
        return self.repository.get_visit_by_audit_id(audit_id)

    def get_visit_audit_context(self, visit_id: int) -> AuditVisitContext | None:
        visit = self.repository.get_visit(visit_id)
        if visit is None:
            return None

        program = self.repository.get_program(visit.program_id)
        if program is None:
            return None

        planned_processes = self.repository.list_visit_processes(visit_id)
        return AuditVisitContext(
            program_id=program.id,
            visit_id=visit.id,
            program_name=program.name.strip(),
            planned_process_ids=tuple(item.process_id for item in planned_processes),
            standards=tuple(self.parse_standards(program.standards_json)),
        )

    def create_audit_from_visit(self, visit_id: int) -> Audit:
        visit = self.repository.get_visit(visit_id)
        if visit is None:
            raise ValueError(f"Návštěva {visit_id} neexistuje.")
        if visit.status == AUDIT_PROGRAM_VISIT_STATUS_SKIPPED:
            raise ValueError("Zrušenou návštěvu nelze auditovat.")
        if visit.audit_id is not None:
            raise ValueError(AUDIT_PROGRAM_VISIT_HAS_AUDIT)

        program = self.repository.get_program(visit.program_id)
        if program is None:
            raise ValueError(f"Program auditů {visit.program_id} neexistuje.")

        from moduly.audity.sluzby.audit_service import audit_service

        workplace_name = self._resolve_workplace_name(visit)
        audit = audit_service.create_audit(
            workplace_id=visit.workplace_id,
            workplace_name=workplace_name,
            year=visit.planned_year or date.today().year,
            planned_month=visit.planned_month,
            audit_date=visit.planned_date,
            started_at=date.today(),
            title=self._build_audit_title(program, visit, workplace_name),
            program_id=program.id,
            program_visit_id=visit.id,
        )

        visit.audit_id = audit.id
        self.repository.update_visit(visit)
        return audit

    def sync_on_audit_completed(self, audit_id: int, *, finished_at: date) -> None:
        visit = self.repository.get_visit_by_audit_id(audit_id)
        if visit is None:
            return

        visit.status = AUDIT_PROGRAM_VISIT_STATUS_COMPLETED
        self.repository.update_visit(visit)

        completed_at = datetime.combine(finished_at, datetime.min.time())
        for visit_process in self.repository.list_visit_processes(visit.id):
            if visit_process.status != AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED:
                continue
            visit_process.status = AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED
            visit_process.audit_id = audit_id
            visit_process.completed_at = completed_at
            self.repository.update_visit_process(visit_process)

    def get_program_overview(self, program_id: int) -> AuditProgramOverview | None:
        program = self.repository.get_program(program_id)
        if program is None:
            return None

        return AuditProgramOverview(
            program=program,
            workplaces=self.repository.list_workplaces(program_id),
            visits=self.repository.list_visits(program_id),
            visit_processes=self.repository.list_program_visit_processes(program_id),
        )

    def get_planned_visits_overview(
        self,
        program_id: int,
    ) -> tuple[PlannedVisitOverviewRow, ...]:
        overview = self.get_program_overview(program_id)
        if overview is None:
            return ()

        workplace_names = {
            workplace.workplace_id: workplace.workplace_name
            for workplace in overview.workplaces
        }
        processes_by_visit: dict[int, list[str]] = {}
        for visit_process in overview.visit_processes:
            label = visit_process.process_name or visit_process.process_id
            processes_by_visit.setdefault(visit_process.visit_id, []).append(label)

        from moduly.audity.sluzby.audit_service import audit_service

        audit_numbers: dict[int, str] = {}
        rows: list[PlannedVisitOverviewRow] = []
        visits = sorted(overview.visits, key=visit_sort_key)

        for visit in visits:
            workplace_name = workplace_names.get(visit.workplace_id, "") or self._resolve_workplace_name(visit)
            sort_date = visit.planned_date
            if sort_date is None and visit.planned_year and visit.planned_month:
                sort_date = date(visit.planned_year, visit.planned_month, 1)

            audit_number = None
            if visit.audit_id is not None:
                if visit.audit_id not in audit_numbers:
                    audit = audit_service.get_by_id(visit.audit_id)
                    audit_numbers[visit.audit_id] = audit.number if audit is not None else ""
                audit_number = audit_numbers.get(visit.audit_id) or None

            process_names = tuple(sorted(processes_by_visit.get(visit.id, [])))
            rows.append(
                PlannedVisitOverviewRow(
                    visit_id=visit.id,
                    planned_date=visit.planned_date,
                    planned_year=visit.planned_year,
                    planned_month=visit.planned_month,
                    sort_date=sort_date,
                    workplace_name=workplace_name,
                    process_names=process_names,
                    status=visit.status,
                    audit_id=visit.audit_id,
                    audit_number=audit_number,
                )
            )

        return tuple(rows)

    def generate_visits(self, program_id: int) -> AuditProgramGenerationResult:
        program = self.repository.get_program(program_id)
        if program is None:
            raise ValueError(f"Program auditů {program_id} neexistuje.")
        if program.date_from is None or program.date_to is None:
            raise ValueError("Program auditů musí mít vyplněné období od/do.")
        if program.manual_planning:
            raise ValueError(AUDIT_PROGRAM_MANUAL_GENERATE_BLOCKED)

        existing_keys = self._existing_visit_keys(program_id)
        created: list[AuditProgramVisit] = []
        skipped = 0

        for workplace in self.repository.list_workplaces(program_id):
            if not workplace.active:
                continue

            planning = self._resolve_workplace_planning_config(workplace)
            if planning is None or not planning.audit_enabled:
                continue

            for planned_year, planned_month in self._plan_workplace_visits(
                program.date_from,
                program.date_to,
                planning,
            ):
                key = (workplace.workplace_id, planned_year, planned_month)
                if key in existing_keys:
                    skipped += 1
                    continue

                visit = self.repository.add_visit(
                    AuditProgramVisit(
                        program_id=program_id,
                        workplace_id=workplace.workplace_id,
                        planned_year=planned_year,
                        planned_month=planned_month,
                        status=DEFAULT_AUDIT_PROGRAM_VISIT_STATUS,
                    )
                )
                existing_keys.add(key)
                created.append(visit)

        return AuditProgramGenerationResult(
            created_visits=tuple(created),
            skipped_existing=skipped,
        )

    def distribute_processes(self, program_id: int) -> AuditProgramDistributionResult:
        program = self.repository.get_program(program_id)
        if program is None:
            raise ValueError(f"Program auditů {program_id} neexistuje.")
        if program.manual_planning:
            raise ValueError(AUDIT_PROGRAM_MANUAL_DISTRIBUTE_BLOCKED)

        processes = self._processes_for_program(program)
        visits = self.repository.list_visits(program_id)
        visit_processes = self.repository.list_program_visit_processes(program_id)

        visits_by_workplace = self._group_visits_by_workplace(visits)
        existing_visit_process_keys = {
            (item.visit_id, item.process_id) for item in visit_processes
        }
        assigned_by_workplace = self._assigned_process_ids_by_workplace(visits, visit_processes)

        created: list[AuditProgramVisitProcess] = []
        skipped = 0

        for workplace in self.repository.list_workplaces(program_id):
            if not workplace.active:
                continue

            workplace_visits = visits_by_workplace.get(workplace.workplace_id, [])
            if not workplace_visits:
                continue

            already_assigned = assigned_by_workplace.get(workplace.workplace_id, set())

            for index, process in enumerate(processes):
                if process.id in already_assigned:
                    skipped += 1
                    continue

                target_visit = workplace_visits[index % len(workplace_visits)]
                key = (target_visit.id, process.id)
                if key in existing_visit_process_keys:
                    skipped += 1
                    already_assigned.add(process.id)
                    continue

                standards = self._resolve_process_standards(process, program)
                visit_process = self.repository.add_visit_process(
                    AuditProgramVisitProcess(
                        visit_id=target_visit.id,
                        process_id=process.id,
                        process_name=process.nazev,
                        standards_json=self.dump_standards(standards),
                        status=DEFAULT_AUDIT_PROGRAM_VISIT_PROCESS_STATUS,
                    )
                )
                existing_visit_process_keys.add(key)
                already_assigned.add(process.id)
                created.append(visit_process)

        return AuditProgramDistributionResult(
            created_processes=tuple(created),
            skipped_existing=skipped,
        )

    def get_program_coverage(self, program_id: int) -> AuditProgramCoverage | None:
        program = self.repository.get_program(program_id)
        if program is None:
            return None

        workplaces = [item for item in self.repository.list_workplaces(program_id) if item.active]
        visits = [
            visit
            for visit in self.repository.list_visits(program_id)
            if visit.status != AUDIT_PROGRAM_VISIT_STATUS_SKIPPED
        ]
        completed_visit_count = sum(
            1 for visit in visits if visit.status == AUDIT_PROGRAM_VISIT_STATUS_COMPLETED
        )
        visit_processes = self.repository.list_program_visit_processes(program_id)
        active_processes = self._processes_for_program(program)
        active_process_ids = {process.id for process in active_processes}

        completed_count = sum(
            1
            for item in visit_processes
            if item.status == AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED
        )
        planned_count = len(visit_processes)
        completion_percent = (
            round(completed_count / planned_count * 100, 2) if planned_count else 0.0
        )

        visits_by_workplace = self._group_visits_by_workplace(visits)
        missing_by_workplace: list[AuditProgramWorkplaceCoverage] = []

        for workplace in workplaces:
            workplace_visit_ids = {
                visit.id for visit in visits_by_workplace.get(workplace.workplace_id, [])
            }
            assigned_process_ids = {
                item.process_id
                for item in visit_processes
                if item.visit_id in workplace_visit_ids
            }
            missing_process_ids = tuple(
                sorted(active_process_ids - assigned_process_ids)
            )
            missing_by_workplace.append(
                AuditProgramWorkplaceCoverage(
                    workplace_id=workplace.workplace_id,
                    workplace_name=workplace.workplace_name,
                    missing_process_ids=missing_process_ids,
                )
            )

        return AuditProgramCoverage(
            workplace_count=len(workplaces),
            visit_count=len(visits),
            completed_visit_count=completed_visit_count,
            planned_process_count=planned_count,
            completed_process_count=completed_count,
            completion_percent=completion_percent,
            missing_by_workplace=tuple(missing_by_workplace),
        )

    def detect_planning_config_changes(self, program_id: int):
        workplaces = self.repository.list_workplaces(program_id)
        return audit_program_planning_config_service.detect_program_planning_changes(
            workplaces
        )

    @staticmethod
    def _plan_workplace_visits(
        date_from: date,
        date_to: date,
        planning: WorkplacePlanningConfig,
    ) -> list[tuple[int, int]]:
        if planning.preferred_months:
            return plan_visit_months(
                date_from,
                date_to,
                planning.audit_interval_months,
                planning.preferred_months,
            )
        return iter_visit_month_anchors(
            date_from,
            date_to,
            planning.audit_interval_months,
        )

    def _resolve_workplace_planning_config(
        self,
        program_workplace: AuditProgramWorkplace,
    ) -> WorkplacePlanningConfig | None:
        current = audit_program_planning_config_service.get_current_config(
            program_workplace.workplace_id
        )
        if current is not None:
            return current

        if program_workplace.workplace_id is None:
            return None

        return WorkplacePlanningConfig(
            workplace_id=program_workplace.workplace_id,
            workplace_name=program_workplace.workplace_name.strip(),
            audit_enabled=True,
            audit_interval_months=int(
                program_workplace.audit_interval_months
                or DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS
            ),
            preferred_months=parse_preferred_months_json(
                program_workplace.preferred_months_json
            ),
        )

    @staticmethod
    def _iter_visit_months(
        date_from: date,
        date_to: date,
        interval_months: int,
    ) -> list[tuple[int, int]]:
        return iter_visit_month_anchors(date_from, date_to, interval_months)

    def _existing_visit_keys(self, program_id: int) -> set[tuple[int | None, int, int]]:
        keys: set[tuple[int | None, int, int]] = set()
        for visit in self.repository.list_visits(program_id):
            if visit.planned_year is None or visit.planned_month is None:
                continue
            keys.add((visit.workplace_id, visit.planned_year, visit.planned_month))
        return keys

    @staticmethod
    def _group_visits_by_workplace(
        visits: list[AuditProgramVisit],
    ) -> dict[int | None, list[AuditProgramVisit]]:
        grouped: dict[int | None, list[AuditProgramVisit]] = {}
        for visit in visits:
            grouped.setdefault(visit.workplace_id, []).append(visit)

        for workplace_id, workplace_visits in grouped.items():
            workplace_visits.sort(
                key=lambda item: (
                    item.planned_year or 0,
                    item.planned_month or 0,
                    item.id,
                )
            )
        return grouped

    @staticmethod
    def _assigned_process_ids_by_workplace(
        visits: list[AuditProgramVisit],
        visit_processes: list[AuditProgramVisitProcess],
    ) -> dict[int | None, set[str]]:
        visit_to_workplace = {visit.id: visit.workplace_id for visit in visits}
        assigned: dict[int | None, set[str]] = {}
        for item in visit_processes:
            workplace_id = visit_to_workplace.get(item.visit_id)
            assigned.setdefault(workplace_id, set()).add(item.process_id)
        return assigned

    def _processes_for_program(self, program: AuditProgram) -> list[AuditProcessDefinition]:
        program_standards = self.parse_standards(program.standards_json)
        return [
            process
            for process in audit_knowledge_service.get_processes()
            if self._process_matches_program_standards(process, program_standards)
        ]

    def _process_matches_program_standards(
        self,
        process: AuditProcessDefinition,
        program_standards: list[str],
    ) -> bool:
        knowledge = audit_knowledge_service.load_process_knowledge(process, ensure=False)
        if knowledge is None:
            return True

        raw_norms = knowledge.get("pozadavky_norem") or []
        if not raw_norms:
            return True

        for item in raw_norms:
            if not isinstance(item, dict):
                continue
            label = str(item.get("nazev") or item.get("id") or "")
            for standard in program_standards:
                if standard in label:
                    return True
        return False

    def _resolve_process_standards(
        self,
        process: AuditProcessDefinition,
        program: AuditProgram,
    ) -> list[str]:
        program_standards = self.parse_standards(program.standards_json)
        knowledge = audit_knowledge_service.load_process_knowledge(process, ensure=False)
        if knowledge is None:
            return list(program_standards)

        raw_norms = knowledge.get("pozadavky_norem") or []
        if not raw_norms:
            return list(program_standards)

        matched: list[str] = []
        for item in raw_norms:
            if not isinstance(item, dict):
                continue
            label = str(item.get("nazev") or item.get("id") or "")
            for standard in program_standards:
                if standard in label and standard not in matched:
                    matched.append(standard)
        return matched or list(program_standards)

    def _mark_manual_planning(self, program_id: int) -> None:
        program = self.repository.get_program(program_id)
        if program is None or program.manual_planning:
            return
        program.manual_planning = True
        self.repository.update_program(program)

    def _resolve_visit_workplace_name(
        self,
        program_id: int,
        visit: AuditProgramVisit,
    ) -> str:
        for workplace in self.repository.list_workplaces(program_id):
            if workplace.workplace_id == visit.workplace_id:
                name = workplace.workplace_name.strip()
                if name:
                    return name
        return self._resolve_workplace_name(visit)

    @staticmethod
    def _resolve_workplace_name(visit: AuditProgramVisit) -> str:
        from moduly.audity.sluzby.audit_service import audit_service

        name = audit_service.resolve_workplace_name(visit.workplace_id)
        if name:
            return name
        return ""

    @staticmethod
    def _build_audit_title(
        program: AuditProgram,
        visit: AuditProgramVisit,
        workplace_name: str,
    ) -> str:
        month = visit.planned_month or 0
        year = visit.planned_year or 0
        if 1 <= month <= 12:
            period = f"{MONTH_NAMES_CAPITALIZED[month - 1]} {year}"
        else:
            period = f"{month}/{year}"

        program_label = program.name.strip() or program.number.strip()
        workplace_label = workplace_name.strip() or "—"
        if program_label:
            return f"{program_label} — {workplace_label} ({period})"
        return f"{workplace_label} ({period})"

    @staticmethod
    def parse_standards(standards_json: str) -> list[str]:
        try:
            parsed = json.loads(standards_json or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed if str(item).strip()]

    @staticmethod
    def dump_standards(standards: list[str]) -> str:
        return json.dumps(list(standards), ensure_ascii=False)

    def _validated_program_fields(self, fields: dict) -> dict:
        name = str(fields.get("name") or "").strip()
        if not name:
            raise ValueError("Název programu auditů je povinný.")

        status = str(fields.get("status") or DEFAULT_AUDIT_PROGRAM_STATUS)
        if status not in AUDIT_PROGRAM_STATUSES:
            raise ValueError(f"Neplatný stav programu auditů: {status}")

        standards = fields.get("standards")
        if standards is None:
            standards_json = self.dump_standards(list(DEFAULT_AUDIT_PROGRAM_STANDARDS))
        elif isinstance(standards, str):
            standards_json = standards
        else:
            standards_json = self.dump_standards([str(item) for item in standards])

        date_from = fields.get("date_from")
        date_to = fields.get("date_to")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("Datum od nesmí být později než datum do.")

        return {
            "number": str(fields.get("number") or "").strip(),
            "name": name,
            "date_from": date_from,
            "date_to": date_to,
            "status": status,
            "standards_json": standards_json,
            "description": str(fields.get("description") or "").strip(),
            "note": str(fields.get("note") or "").strip(),
            "created_at": fields.get("created_at") or datetime.now(),
            "approved_at": fields.get("approved_at"),
            "closed_at": fields.get("closed_at"),
            "manual_planning": bool(fields.get("manual_planning", False)),
        }

    def _validated_workplace_fields(self, fields: dict) -> dict:
        interval = int(
            fields.get("audit_interval_months") or DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS
        )
        if interval <= 0:
            raise ValueError("Interval auditu pracoviště musí být kladný.")

        preferred_months_json = fields.get("preferred_months_json")
        if preferred_months_json is None:
            preferred_months_json = "[]"
        elif not isinstance(preferred_months_json, str):
            preferred_months_json = str(preferred_months_json)

        return {
            "workplace_id": fields.get("workplace_id"),
            "workplace_name": str(fields.get("workplace_name") or "").strip(),
            "audit_interval_months": interval,
            "preferred_months_json": preferred_months_json,
            "active": bool(fields.get("active", True)),
            "note": str(fields.get("note") or "").strip(),
        }

    def _validated_visit_fields(self, fields: dict) -> dict:
        status = str(fields.get("status") or DEFAULT_AUDIT_PROGRAM_VISIT_STATUS)
        if status not in AUDIT_PROGRAM_VISIT_STATUSES:
            raise ValueError(f"Neplatný stav návštěvy: {status}")

        planned_month = fields.get("planned_month")
        if planned_month is not None:
            planned_month = int(planned_month)
            if planned_month < 1 or planned_month > 12:
                raise ValueError("Plánovaný měsíc musí být v rozsahu 1–12.")

        return {
            "workplace_id": fields.get("workplace_id"),
            "planned_year": fields.get("planned_year"),
            "planned_month": planned_month,
            "planned_date": fields.get("planned_date"),
            "status": status,
            "audit_id": fields.get("audit_id"),
            "note": str(fields.get("note") or "").strip(),
        }

    def _validated_visit_process_fields(self, fields: dict) -> dict:
        process_id = str(fields.get("process_id") or "").strip()
        if not process_id:
            raise ValueError("Identifikátor řídicího procesu je povinný.")

        status = str(fields.get("status") or DEFAULT_AUDIT_PROGRAM_VISIT_PROCESS_STATUS)
        if status not in AUDIT_PROGRAM_VISIT_PROCESS_STATUSES:
            raise ValueError(f"Neplatný stav plánovaného procesu: {status}")

        standards = fields.get("standards")
        if standards is None:
            standards_json = self.dump_standards(list(DEFAULT_AUDIT_PROGRAM_STANDARDS))
        elif isinstance(standards, str):
            standards_json = standards
        else:
            standards_json = self.dump_standards([str(item) for item in standards])

        return {
            "process_id": process_id,
            "process_name": str(fields.get("process_name") or "").strip(),
            "standards_json": standards_json,
            "status": status,
            "audit_id": fields.get("audit_id"),
            "completed_at": fields.get("completed_at"),
            "note": str(fields.get("note") or "").strip(),
        }

    @staticmethod
    def _make_number(program_id: int) -> str:
        return f"PA-{program_id:04d}"


audit_program_service = AuditProgramService()
