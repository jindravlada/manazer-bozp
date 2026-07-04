from moduly.audity.constants import AUDIT_PROGRAM_VISIT_STATUS_SKIPPED
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_program import AuditProgram
from moduly.audity.repository.audit_program_repository import AuditProgramRepository
from moduly.audity.sluzby.audit_program_service import audit_program_service


class AuditAnnualProgramService:
    def __init__(self) -> None:
        self.repository = AuditProgramRepository()

    def list_programs_for_year(self, year: int) -> list[AuditProgram]:
        programs: list[AuditProgram] = []
        for program in audit_program_service.list_programs():
            visits = [
                visit
                for visit in self.repository.list_visits(program.id)
                if visit.planned_year == year and visit.status != AUDIT_PROGRAM_VISIT_STATUS_SKIPPED
            ]
            if visits:
                programs.append(program)
        return sorted(programs, key=lambda item: (item.name.casefold(), item.id))

    def get_program_by_id(self, program_id: int | None) -> AuditProgram | None:
        if program_id is None:
            return None
        for program in audit_program_service.list_programs():
            if program.id == program_id:
                return program
        return None

    def resolve_program_id(self, year: int, program_id: int | None) -> int:
        programs = self.list_programs_for_year(year)
        if not programs:
            raise ValueError(
                f"Pro rok {year} není evidován žádný auditní program. "
                "Nejprve vytvořte auditní program s návštěvami v daném roce."
            )
        if len(programs) == 1:
            return programs[0].id
        if program_id is None:
            raise ValueError("Vyberte auditní program pro roční zprávu.")
        valid_ids = {program.id for program in programs}
        if program_id not in valid_ids:
            raise ValueError("Vybraný auditní program není pro zvolený rok platný.")
        return program_id

    def filter_audits_for_program(
        self,
        audits: list[Audit],
        *,
        program_id: int | None,
    ) -> list[Audit]:
        if program_id is None:
            return audits

        linked_audit_ids = {
            visit.audit_id
            for visit in self.repository.list_visits(program_id)
            if visit.audit_id is not None
        }
        return [
            audit
            for audit in audits
            if audit.program_id == program_id or audit.id in linked_audit_ids
        ]


audit_annual_program_service = AuditAnnualProgramService()
