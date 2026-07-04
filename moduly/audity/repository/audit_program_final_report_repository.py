from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.modely.audit_program_final_report import AuditProgramFinalReport


class AuditProgramFinalReportRepository:
    def get_by_program_id(self, audit_program_id: int) -> AuditProgramFinalReport | None:
        with get_session() as session:
            stmt = (
                select(AuditProgramFinalReport)
                .where(AuditProgramFinalReport.audit_program_id == audit_program_id)
            )
            return session.scalars(stmt).first()

    def get_last_with_preparer(self) -> AuditProgramFinalReport | None:
        with get_session() as session:
            stmt = (
                select(AuditProgramFinalReport)
                .where(AuditProgramFinalReport.zpracoval_worker_id.isnot(None))
                .order_by(
                    AuditProgramFinalReport.updated_at.desc(),
                    AuditProgramFinalReport.id.desc(),
                )
            )
            return session.scalars(stmt).first()

    def save(self, report: AuditProgramFinalReport) -> AuditProgramFinalReport:
        with get_session() as session:
            stmt = (
                select(AuditProgramFinalReport)
                .where(AuditProgramFinalReport.audit_program_id == report.audit_program_id)
            )
            existing = session.scalars(stmt).first()
            if existing is None:
                session.add(report)
                session.commit()
                session.refresh(report)
                return report

            existing.silne_stranky = report.silne_stranky
            existing.hlavni_slabiny = report.hlavni_slabiny
            existing.doporuceni_novy_program = report.doporuceni_novy_program
            existing.zpracoval = report.zpracoval
            existing.zpracoval_worker_id = report.zpracoval_worker_id
            session.commit()
            session.refresh(existing)
            return existing
