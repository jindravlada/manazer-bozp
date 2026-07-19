from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_workplace import CoordinationWorkplace


class CoordinationWorkplaceRepository:
    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationWorkplace]:
        with get_session() as session:
            stmt = select(CoordinationWorkplace).where(
                CoordinationWorkplace.coordination_id == coordination_id,
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationWorkplace.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationWorkplace.sort_order,
                CoordinationWorkplace.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, workplace_link_id: int) -> CoordinationWorkplace | None:
        with get_session() as session:
            return session.get(CoordinationWorkplace, workplace_link_id)

    def add(self, item: CoordinationWorkplace) -> CoordinationWorkplace:
        with get_session() as session:
            session.add(item)
            session.commit()
            session.refresh(item)
            return item

    def update(self, item: CoordinationWorkplace) -> CoordinationWorkplace:
        with get_session() as session:
            item = session.merge(item)
            session.commit()
            session.refresh(item)
            return item

    def next_sort_order(self, coordination_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(CoordinationWorkplace.sort_order)
                .where(CoordinationWorkplace.coordination_id == coordination_id)
                .order_by(CoordinationWorkplace.sort_order.desc())
            )
            current = session.scalar(stmt)
            return (current or 0) + 1
