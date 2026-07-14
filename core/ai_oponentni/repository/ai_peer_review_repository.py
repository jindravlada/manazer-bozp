from sqlalchemy import select

from core.ai_oponentni.modely.ai_peer_review import AiPeerReview
from core.database.session import get_session


class AiPeerReviewRepository:
    def get_for_source(self, source_type: str, source_id: int) -> list[AiPeerReview]:
        with get_session() as session:
            stmt = (
                select(AiPeerReview)
                .where(
                    AiPeerReview.source_type == source_type,
                    AiPeerReview.source_id == source_id,
                )
                .order_by(AiPeerReview.exported_at.desc(), AiPeerReview.id.desc())
            )
            return list(session.scalars(stmt))

    def get_by_id(self, review_id: int) -> AiPeerReview | None:
        with get_session() as session:
            return session.get(AiPeerReview, review_id)

    def add(self, review: AiPeerReview) -> AiPeerReview:
        with get_session() as session:
            session.add(review)
            session.commit()
            session.refresh(review)
            return review

    def update(self, review: AiPeerReview) -> AiPeerReview:
        with get_session() as session:
            review = session.merge(review)
            session.commit()
            session.refresh(review)
            return review
