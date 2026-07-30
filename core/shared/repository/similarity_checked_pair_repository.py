"""Repository evidence zkontrolovaných dvojic (SIMILARITY-3)."""

from __future__ import annotations

from sqlalchemy import delete, select

from core.database.session import get_session
from core.shared.modely.similarity_checked_pair import SimilarityCheckedPair


class SimilarityCheckedPairRepository:
    def get(
        self,
        entity_type: str,
        left_entity_id: str,
        right_entity_id: str,
    ) -> SimilarityCheckedPair | None:
        with get_session() as session:
            stmt = select(SimilarityCheckedPair).where(
                SimilarityCheckedPair.entity_type == entity_type,
                SimilarityCheckedPair.left_entity_id == left_entity_id,
                SimilarityCheckedPair.right_entity_id == right_entity_id,
            )
            return session.scalars(stmt).first()

    def list_for_type(self, entity_type: str) -> list[SimilarityCheckedPair]:
        with get_session() as session:
            stmt = (
                select(SimilarityCheckedPair)
                .where(SimilarityCheckedPair.entity_type == entity_type)
                .order_by(SimilarityCheckedPair.checked_at.desc(), SimilarityCheckedPair.id)
            )
            return list(session.scalars(stmt))

    def add(self, record: SimilarityCheckedPair) -> SimilarityCheckedPair:
        with get_session() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            session.expunge(record)
            return record

    def delete(
        self,
        entity_type: str,
        left_entity_id: str,
        right_entity_id: str,
    ) -> bool:
        with get_session() as session:
            stmt = delete(SimilarityCheckedPair).where(
                SimilarityCheckedPair.entity_type == entity_type,
                SimilarityCheckedPair.left_entity_id == left_entity_id,
                SimilarityCheckedPair.right_entity_id == right_entity_id,
            )
            result = session.execute(stmt)
            session.commit()
            return bool(result.rowcount)
