from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.modely.audit_annual_report import AuditAnnualReport


class AuditAnnualReportRepository:
    def get_by_year_and_program(
        self,
        year: int,
        audit_program_id: int | None,
    ) -> AuditAnnualReport | None:
        with get_session() as session:
            stmt = select(AuditAnnualReport).where(AuditAnnualReport.year == year)
            if audit_program_id is None:
                stmt = stmt.where(AuditAnnualReport.audit_program_id.is_(None))
            else:
                stmt = stmt.where(AuditAnnualReport.audit_program_id == audit_program_id)
            return session.scalars(stmt).first()

    def get_by_year(self, year: int) -> AuditAnnualReport | None:
        return self.get_by_year_and_program(year, None)

    def get_last_with_preparer(self) -> AuditAnnualReport | None:
        with get_session() as session:
            stmt = (
                select(AuditAnnualReport)
                .where(AuditAnnualReport.zpracoval_worker_id.isnot(None))
                .order_by(AuditAnnualReport.updated_at.desc(), AuditAnnualReport.id.desc())
            )
            return session.scalars(stmt).first()

    def save(self, report: AuditAnnualReport) -> AuditAnnualReport:
        with get_session() as session:
            stmt = select(AuditAnnualReport).where(AuditAnnualReport.year == report.year)
            if report.audit_program_id is None:
                stmt = stmt.where(AuditAnnualReport.audit_program_id.is_(None))
            else:
                stmt = stmt.where(AuditAnnualReport.audit_program_id == report.audit_program_id)
            existing = session.scalars(stmt).first()
            if existing is None:
                session.add(report)
                session.commit()
                session.refresh(report)
                return report

            existing.silne_stranky = report.silne_stranky
            existing.top_priority = report.top_priority
            existing.doporuceni_specialisty = report.doporuceni_specialisty
            existing.zpracoval = report.zpracoval
            existing.zpracoval_worker_id = report.zpracoval_worker_id
            existing.audit_program_id = report.audit_program_id
            session.commit()
            session.refresh(existing)
            return existing
