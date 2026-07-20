from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
from moduly.koordinace_bozp.modely.coordination_participant import (
    CoordinationParticipant,
)


class CoordinationParticipantRepository:
    def list_for_employer(
        self,
        coordination_employer_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationParticipant]:
        with get_session() as session:
            stmt = select(CoordinationParticipant).where(
                CoordinationParticipant.coordination_employer_id
                == coordination_employer_id,
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationParticipant.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationParticipant.sort_order,
                CoordinationParticipant.full_name,
                CoordinationParticipant.id,
            )
            return list(session.scalars(stmt))

    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationParticipant]:
        with get_session() as session:
            stmt = (
                select(CoordinationParticipant)
                .join(
                    CoordinationEmployer,
                    CoordinationEmployer.id
                    == CoordinationParticipant.coordination_employer_id,
                )
                .where(CoordinationEmployer.coordination_id == coordination_id)
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationParticipant.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationEmployer.sort_order,
                CoordinationEmployer.company_name,
                CoordinationEmployer.id,
                CoordinationParticipant.full_name,
                CoordinationParticipant.role,
                CoordinationParticipant.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, participant_id: int) -> CoordinationParticipant | None:
        with get_session() as session:
            return session.get(CoordinationParticipant, participant_id)

    def add(self, participant: CoordinationParticipant) -> CoordinationParticipant:
        with get_session() as session:
            session.add(participant)
            session.commit()
            session.refresh(participant)
            return participant

    def update(
        self,
        participant: CoordinationParticipant,
    ) -> CoordinationParticipant:
        with get_session() as session:
            participant = session.merge(participant)
            session.commit()
            session.refresh(participant)
            return participant

    def next_sort_order(self, coordination_employer_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(CoordinationParticipant.sort_order)
                .where(
                    CoordinationParticipant.coordination_employer_id
                    == coordination_employer_id,
                )
                .order_by(CoordinationParticipant.sort_order.desc())
            )
            current = session.scalar(stmt)
            return (current or 0) + 1
