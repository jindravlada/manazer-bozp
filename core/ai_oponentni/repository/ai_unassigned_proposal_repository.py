from sqlalchemy import delete, select

from core.ai_oponentni.modely.ai_unassigned_proposal import (
    AiUnassignedProposal,
    PROPOSAL_STATUS_PENDING,
)
from core.database.session import get_session


class AiUnassignedProposalRepository:
    def get_for_review(self, ai_peer_review_id: int) -> list[AiUnassignedProposal]:
        with get_session() as session:
            stmt = (
                select(AiUnassignedProposal)
                .where(AiUnassignedProposal.ai_peer_review_id == ai_peer_review_id)
                .order_by(AiUnassignedProposal.id)
            )
            return list(session.scalars(stmt))

    def get_for_source(self, source_type: str, source_id: int) -> list[AiUnassignedProposal]:
        with get_session() as session:
            stmt = (
                select(AiUnassignedProposal)
                .where(
                    AiUnassignedProposal.source_type == source_type,
                    AiUnassignedProposal.source_id == source_id,
                )
                .order_by(AiUnassignedProposal.id)
            )
            return list(session.scalars(stmt))

    def delete_for_review(self, ai_peer_review_id: int) -> None:
        with get_session() as session:
            session.execute(
                delete(AiUnassignedProposal).where(
                    AiUnassignedProposal.ai_peer_review_id == ai_peer_review_id,
                ),
            )
            session.commit()

    def add(self, proposal: AiUnassignedProposal) -> AiUnassignedProposal:
        with get_session() as session:
            session.add(proposal)
            session.commit()
            session.refresh(proposal)
            return proposal

    def add_many(self, proposals: list[AiUnassignedProposal]) -> list[AiUnassignedProposal]:
        if not proposals:
            return []
        with get_session() as session:
            session.add_all(proposals)
            session.commit()
            for proposal in proposals:
                session.refresh(proposal)
            return proposals

    def get_by_id(self, proposal_id: int) -> AiUnassignedProposal | None:
        with get_session() as session:
            return session.get(AiUnassignedProposal, proposal_id)

    def get_by_ids(self, proposal_ids: list[int]) -> list[AiUnassignedProposal]:
        if not proposal_ids:
            return []
        with get_session() as session:
            stmt = (
                select(AiUnassignedProposal)
                .where(AiUnassignedProposal.id.in_(proposal_ids))
                .order_by(AiUnassignedProposal.id)
            )
            return list(session.scalars(stmt))

    def get_pending_for_review(self, ai_peer_review_id: int) -> list[AiUnassignedProposal]:
        with get_session() as session:
            stmt = (
                select(AiUnassignedProposal)
                .where(
                    AiUnassignedProposal.ai_peer_review_id == ai_peer_review_id,
                    AiUnassignedProposal.status == PROPOSAL_STATUS_PENDING,
                )
                .order_by(AiUnassignedProposal.id)
            )
            return list(session.scalars(stmt))

    def update(self, proposal: AiUnassignedProposal) -> AiUnassignedProposal:
        with get_session() as session:
            proposal = session.merge(proposal)
            session.commit()
            session.refresh(proposal)
            return proposal
