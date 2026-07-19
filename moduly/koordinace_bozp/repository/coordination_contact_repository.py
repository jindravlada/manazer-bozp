from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact


class CoordinationContactRepository:
    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationContact]:
        with get_session() as session:
            stmt = select(CoordinationContact).where(
                CoordinationContact.coordination_id == coordination_id,
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationContact.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationContact.sort_order,
                CoordinationContact.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, contact_id: int) -> CoordinationContact | None:
        with get_session() as session:
            return session.get(CoordinationContact, contact_id)

    def add(self, contact: CoordinationContact) -> CoordinationContact:
        with get_session() as session:
            session.add(contact)
            session.commit()
            session.refresh(contact)
            return contact

    def update(self, contact: CoordinationContact) -> CoordinationContact:
        with get_session() as session:
            contact = session.merge(contact)
            session.commit()
            session.refresh(contact)
            return contact

    def next_sort_order(self, coordination_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(CoordinationContact.sort_order)
                .where(CoordinationContact.coordination_id == coordination_id)
                .order_by(CoordinationContact.sort_order.desc())
            )
            current = session.scalar(stmt)
            return (current or 0) + 1
