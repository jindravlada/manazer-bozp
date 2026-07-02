import calendar
import json
from dataclasses import dataclass
from datetime import date, datetime

from moduly.audity.constants import (
    AUDIT_PROGRAM_STATUSES,
    AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_PROCESS_STATUSES,
    AUDIT_PROGRAM_VISIT_STATUSES,
    DEFAULT_AUDIT_PROGRAM_STANDARDS,
    DEFAULT_AUDIT_PROGRAM_STATUS,
    DEFAULT_AUDIT_PROGRAM_VISIT_PROCESS_STATUS,
    DEFAULT_AUDIT_PROGRAM_VISIT_STATUS,
)
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
    planned_process_count: int
    completed_process_count: int
    completion_percent: float
    missing_by_workplace: tuple[AuditProgramWorkplaceCoverage, ...]


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

    def get_program(self, program_id: int) -> AuditProgram | None:
        return self.repository.get_program(program_id)

    def list_programs(self) -> list[AuditProgram]:
        return self.repository.list_programs()

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
            if workplace.id in existing_ids:
                continue
            self.add_workplace(
                program_id,
                workplace_id=workplace.id,
                workplace_name=workplace.name,
                audit_interval_months=12,
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

    def generate_visits(self, program_id: int) -> AuditProgramGenerationResult:
        program = self.repository.get_program(program_id)
        if program is None:
            raise ValueError(f"Program auditů {program_id} neexistuje.")
        if program.date_from is None or program.date_to is None:
            raise ValueError("Program auditů musí mít vyplněné období od/do.")

        existing_keys = self._existing_visit_keys(program_id)
        created: list[AuditProgramVisit] = []
        skipped = 0

        for workplace in self.repository.list_workplaces(program_id):
            if not workplace.active:
                continue

            for planned_year, planned_month in self._iter_visit_months(
                program.date_from,
                program.date_to,
                workplace.audit_interval_months,
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
        visits = self.repository.list_visits(program_id)
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
            planned_process_count=planned_count,
            completed_process_count=completed_count,
            completion_percent=completion_percent,
            missing_by_workplace=tuple(missing_by_workplace),
        )

    @staticmethod
    def _iter_visit_months(
        date_from: date,
        date_to: date,
        interval_months: int,
    ) -> list[tuple[int, int]]:
        if interval_months <= 0:
            raise ValueError("Interval auditu pracoviště musí být kladný.")

        slots: list[tuple[int, int]] = []
        year = date_from.year
        month = date_from.month

        while True:
            first_of_month = date(year, month, 1)
            if first_of_month > date_to:
                break

            last_day = calendar.monthrange(year, month)[1]
            last_of_month = date(year, month, last_day)
            if last_of_month >= date_from:
                slots.append((year, month))

            year, month = AuditProgramService._add_months(year, month, interval_months)

        return slots

    @staticmethod
    def _add_months(year: int, month: int, months: int) -> tuple[int, int]:
        total_month_index = year * 12 + (month - 1) + months
        return total_month_index // 12, total_month_index % 12 + 1

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
        }

    def _validated_workplace_fields(self, fields: dict) -> dict:
        interval = int(fields.get("audit_interval_months") or 12)
        if interval <= 0:
            raise ValueError("Interval auditu pracoviště musí být kladný.")

        return {
            "workplace_id": fields.get("workplace_id"),
            "workplace_name": str(fields.get("workplace_name") or "").strip(),
            "audit_interval_months": interval,
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
