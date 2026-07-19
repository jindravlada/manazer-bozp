from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer


class CoordinationEmployerRepository:
    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationEmployer]:
        with get_session() as session:
            stmt = select(CoordinationEmployer).where(
                CoordinationEmployer.coordination_id == coordination_id,
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationEmployer.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationEmployer.sort_order,
                CoordinationEmployer.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, employer_id: int) -> CoordinationEmployer | None:
        with get_session() as session:
            return session.get(CoordinationEmployer, employer_id)

    def add(self, employer: CoordinationEmployer) -> CoordinationEmployer:
        with get_session() as session:
            session.add(employer)
            session.commit()
            session.refresh(employer)
            return employer

    def update(self, employer: CoordinationEmployer) -> CoordinationEmployer:
        with get_session() as session:
            employer = session.merge(employer)
            session.commit()
            session.refresh(employer)
            return employer

    def next_sort_order(self, coordination_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(CoordinationEmployer.sort_order)
                .where(CoordinationEmployer.coordination_id == coordination_id)
                .order_by(CoordinationEmployer.sort_order.desc())
            )
            current = session.scalar(stmt)
            return (current or 0) + 1

    def get_main(self, coordination_id: int) -> CoordinationEmployer | None:
        with get_session() as session:
            stmt = select(CoordinationEmployer).where(
                CoordinationEmployer.coordination_id == coordination_id,
                CoordinationEmployer.is_main == True,  # noqa: E712
            )
            return session.scalars(stmt).first()
