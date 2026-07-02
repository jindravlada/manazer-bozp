from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.modely.audit_program import (
    AuditProgram,
    AuditProgramVisit,
    AuditProgramVisitProcess,
    AuditProgramWorkplace,
)


class AuditProgramRepository:
    def list_programs(self) -> list[AuditProgram]:
        with get_session() as session:
            stmt = select(AuditProgram).order_by(
                AuditProgram.date_from.desc(),
                AuditProgram.id.desc(),
            )
            return list(session.scalars(stmt))

    def get_program(self, program_id: int) -> AuditProgram | None:
        with get_session() as session:
            return session.get(AuditProgram, program_id)

    def add_program(self, program: AuditProgram) -> AuditProgram:
        with get_session() as session:
            session.add(program)
            session.commit()
            session.refresh(program)
            return program

    def update_program(self, program: AuditProgram) -> AuditProgram:
        with get_session() as session:
            program = session.merge(program)
            session.commit()
            session.refresh(program)
            return program

    def add_workplace(self, workplace: AuditProgramWorkplace) -> AuditProgramWorkplace:
        with get_session() as session:
            session.add(workplace)
            session.commit()
            session.refresh(workplace)
            return workplace

    def list_workplaces(self, program_id: int) -> list[AuditProgramWorkplace]:
        with get_session() as session:
            stmt = (
                select(AuditProgramWorkplace)
                .where(AuditProgramWorkplace.program_id == program_id)
                .order_by(AuditProgramWorkplace.workplace_name, AuditProgramWorkplace.id)
            )
            return list(session.scalars(stmt))

    def add_visit(self, visit: AuditProgramVisit) -> AuditProgramVisit:
        with get_session() as session:
            session.add(visit)
            session.commit()
            session.refresh(visit)
            return visit

    def list_visits(self, program_id: int) -> list[AuditProgramVisit]:
        with get_session() as session:
            stmt = (
                select(AuditProgramVisit)
                .where(AuditProgramVisit.program_id == program_id)
                .order_by(
                    AuditProgramVisit.planned_year,
                    AuditProgramVisit.planned_month,
                    AuditProgramVisit.id,
                )
            )
            return list(session.scalars(stmt))

    def get_visit(self, visit_id: int) -> AuditProgramVisit | None:
        with get_session() as session:
            return session.get(AuditProgramVisit, visit_id)

    def add_visit_process(
        self,
        visit_process: AuditProgramVisitProcess,
    ) -> AuditProgramVisitProcess:
        with get_session() as session:
            session.add(visit_process)
            session.commit()
            session.refresh(visit_process)
            return visit_process

    def list_visit_processes(self, visit_id: int) -> list[AuditProgramVisitProcess]:
        with get_session() as session:
            stmt = (
                select(AuditProgramVisitProcess)
                .where(AuditProgramVisitProcess.visit_id == visit_id)
                .order_by(AuditProgramVisitProcess.process_name, AuditProgramVisitProcess.id)
            )
            return list(session.scalars(stmt))

    def list_program_visit_processes(self, program_id: int) -> list[AuditProgramVisitProcess]:
        with get_session() as session:
            stmt = (
                select(AuditProgramVisitProcess)
                .join(
                    AuditProgramVisit,
                    AuditProgramVisitProcess.visit_id == AuditProgramVisit.id,
                )
                .where(AuditProgramVisit.program_id == program_id)
                .order_by(
                    AuditProgramVisitProcess.process_name,
                    AuditProgramVisitProcess.id,
                )
            )
            return list(session.scalars(stmt))
