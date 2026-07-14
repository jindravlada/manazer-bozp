from sqlalchemy import select

from core.ai_oponentni.modely.ai_peer_review import AiPeerReviewBatch
from core.database.session import get_session


class AiPeerReviewBatchRepository:
    def get_for_review(self, ai_peer_review_id: int) -> list[AiPeerReviewBatch]:
        with get_session() as session:
            stmt = (
                select(AiPeerReviewBatch)
                .where(AiPeerReviewBatch.ai_peer_review_id == ai_peer_review_id)
                .order_by(AiPeerReviewBatch.batch_number, AiPeerReviewBatch.id)
            )
            return list(session.scalars(stmt))

    def add_many(self, batches: list[AiPeerReviewBatch]) -> list[AiPeerReviewBatch]:
        if not batches:
            return []
        with get_session() as session:
            session.add_all(batches)
            session.commit()
            for batch in batches:
                session.refresh(batch)
            return batches
