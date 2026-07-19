from sqlalchemy import select, update

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
    CoordinationPbpRevision,
)


class CoordinationPbpRevisionRepository:
    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationPbpRevision]:
        with get_session() as session:
            stmt = select(CoordinationPbpRevision).where(
                CoordinationPbpRevision.coordination_id == coordination_id,
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationPbpRevision.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationPbpRevision.revision_number.desc(),
                CoordinationPbpRevision.id.desc(),
            )
            return list(session.scalars(stmt))

    def get_current(self, coordination_id: int) -> CoordinationPbpRevision | None:
        with get_session() as session:
            stmt = (
                select(CoordinationPbpRevision)
                .where(
                    CoordinationPbpRevision.coordination_id == coordination_id,
                    CoordinationPbpRevision.is_current == True,  # noqa: E712
                    CoordinationPbpRevision.active == True,  # noqa: E712
                )
                .order_by(CoordinationPbpRevision.revision_number.desc())
            )
            return session.scalars(stmt).first()

    def get_by_id(self, revision_id: int) -> CoordinationPbpRevision | None:
        with get_session() as session:
            return session.get(CoordinationPbpRevision, revision_id)

    def next_revision_number(self, coordination_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(CoordinationPbpRevision.revision_number)
                .where(CoordinationPbpRevision.coordination_id == coordination_id)
                .order_by(CoordinationPbpRevision.revision_number.desc())
            )
            current = session.scalar(stmt)
            return (current or 0) + 1

    def clear_current(self, coordination_id: int) -> None:
        with get_session() as session:
            session.execute(
                update(CoordinationPbpRevision)
                .where(CoordinationPbpRevision.coordination_id == coordination_id)
                .values(is_current=False)
            )
            session.commit()

    def add(self, revision: CoordinationPbpRevision) -> CoordinationPbpRevision:
        with get_session() as session:
            session.add(revision)
            session.commit()
            session.refresh(revision)
            return revision
