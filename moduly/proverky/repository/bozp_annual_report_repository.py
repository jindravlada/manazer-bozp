from sqlalchemy import select

from core.database.session import get_session
from moduly.proverky.modely.bozp_annual_report import BozpAnnualReport


class BozpAnnualReportRepository:
    def get_by_year(self, year: int) -> BozpAnnualReport | None:
        with get_session() as session:
            stmt = select(BozpAnnualReport).where(BozpAnnualReport.year == year)
            return session.scalars(stmt).first()

    def save(self, report: BozpAnnualReport) -> BozpAnnualReport:
        with get_session() as session:
            existing = session.scalars(
                select(BozpAnnualReport).where(BozpAnnualReport.year == report.year)
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
            session.commit()
            session.refresh(existing)
            return existing
