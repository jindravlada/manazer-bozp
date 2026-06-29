from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from moduly.kontroly.modely.thp_monthly_control import ThpMonthlyControl


class MonthlyControlRepository:
    def get_by_year(self, year: int) -> list[ThpMonthlyControl]:
        with get_session() as session:
            stmt = (
                select(ThpMonthlyControl)
                .where(ThpMonthlyControl.year == year)
                .order_by(
                    ThpMonthlyControl.thp_worker_id,
                    ThpMonthlyControl.month,
                )
            )
            return list(session.scalars(stmt))

    def get_by_key(self, year: int, month: int, thp_worker_id: int) -> ThpMonthlyControl | None:
        with get_session() as session:
            stmt = select(ThpMonthlyControl).where(
                ThpMonthlyControl.year == year,
                ThpMonthlyControl.month == month,
                ThpMonthlyControl.thp_worker_id == thp_worker_id,
            )
            return session.scalars(stmt).first()

    def save(self, record: ThpMonthlyControl) -> ThpMonthlyControl:
        with get_session() as session:
            record.updated_at = datetime.now()
            record = session.merge(record)
            session.commit()
            session.refresh(record)
            return record
