import json
from dataclasses import dataclass
from datetime import datetime

from moduly.audity.constants import (
    AUDIT_PROGRAM_STATUSES,
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


@dataclass(frozen=True)
class AuditProgramOverview:
    program: AuditProgram
    workplaces: list[AuditProgramWorkplace]
    visits: list[AuditProgramVisit]
    visit_processes: list[AuditProgramVisitProcess]


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
