from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview


class RiskMeasureReviewRepository:
    def get_all(self, *, include_archived: bool = True) -> list[RiskMeasureReview]:
        with get_session() as session:
            stmt = select(RiskMeasureReview)
            if not include_archived:
                stmt = stmt.where(RiskMeasureReview.archived_at.is_(None))
            stmt = stmt.order_by(
                RiskMeasureReview.review_date.desc(),
                RiskMeasureReview.id.desc(),
            )
            return list(session.scalars(stmt))

    def get_by_id(self, review_id: int) -> RiskMeasureReview | None:
        with get_session() as session:
            return session.get(RiskMeasureReview, review_id)

    def add(self, review: RiskMeasureReview) -> RiskMeasureReview:
        with get_session() as session:
            session.add(review)
            session.commit()
            session.refresh(review)
            return review

    def update(self, review: RiskMeasureReview) -> RiskMeasureReview:
        with get_session() as session:
            review = session.merge(review)
            session.commit()
            session.refresh(review)
            return review

    def allocate_next_number(self, year: int | None = None) -> str:
        target_year = year or datetime.now().year
        prefix = f"{target_year}-"
        with get_session() as session:
            stmt = select(RiskMeasureReview.review_number).where(
                RiskMeasureReview.review_number.like(f"{prefix}%")
            )
            max_sequence = 0
            for number in session.scalars(stmt):
                if not number:
                    continue
                try:
                    _, suffix = number.split("-", 1)
                    max_sequence = max(max_sequence, int(suffix))
                except (ValueError, IndexError):
                    continue
            return f"{target_year}-{max_sequence + 1:04d}"
