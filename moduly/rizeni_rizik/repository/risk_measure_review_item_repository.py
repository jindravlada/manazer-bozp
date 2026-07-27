from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem


class RiskMeasureReviewItemRepository:
    def list_for_review(self, review_id: int) -> list[RiskMeasureReviewItem]:
        with get_session() as session:
            stmt = (
                select(RiskMeasureReviewItem)
                .where(RiskMeasureReviewItem.review_id == review_id)
                .order_by(
                    RiskMeasureReviewItem.sort_order,
                    RiskMeasureReviewItem.id,
                )
            )
            return list(session.scalars(stmt))

    def replace_items(
        self,
        review_id: int,
        items: list[RiskMeasureReviewItem],
    ) -> None:
        with get_session() as session:
            session.execute(
                delete(RiskMeasureReviewItem).where(
                    RiskMeasureReviewItem.review_id == review_id,
                ),
            )
            for item in items:
                item.review_id = review_id
                session.add(item)
            session.commit()
