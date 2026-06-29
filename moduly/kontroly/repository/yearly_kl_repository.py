from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from moduly.kontroly.modely.thp_yearly_kl_usage import ThpYearlyKlUsage


class YearlyKlRepository:
    def get_by_year(self, year: int) -> list[ThpYearlyKlUsage]:
        with get_session() as session:
            stmt = (
                select(ThpYearlyKlUsage)
                .where(ThpYearlyKlUsage.year == year)
                .order_by(ThpYearlyKlUsage.thp_worker_id)
            )
            return list(session.scalars(stmt))

    def get_by_key(self, year: int, thp_worker_id: int) -> ThpYearlyKlUsage | None:
        with get_session() as session:
            stmt = select(ThpYearlyKlUsage).where(
                ThpYearlyKlUsage.year == year,
                ThpYearlyKlUsage.thp_worker_id == thp_worker_id,
            )
            return session.scalars(stmt).first()

    def save(self, record: ThpYearlyKlUsage) -> ThpYearlyKlUsage:
        with get_session() as session:
            record.updated_at = datetime.now()
            record = session.merge(record)
            session.commit()
            session.refresh(record)
            return record
