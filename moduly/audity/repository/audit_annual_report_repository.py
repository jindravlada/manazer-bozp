from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.modely.audit_annual_report import AuditAnnualReport


class AuditAnnualReportRepository:
    def get_by_year(self, year: int) -> AuditAnnualReport | None:
        with get_session() as session:
            stmt = select(AuditAnnualReport).where(AuditAnnualReport.year == year)
            return session.scalars(stmt).first()

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
            existing = session.scalars(
                select(AuditAnnualReport).where(AuditAnnualReport.year == report.year)
            ).first()
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
            session.commit()
            session.refresh(existing)
            return existing
