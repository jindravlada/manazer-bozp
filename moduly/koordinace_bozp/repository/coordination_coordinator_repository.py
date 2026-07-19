from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_coordinator import (
    CoordinationCoordinator,
)


class CoordinationCoordinatorRepository:
    def get_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = False,
    ) -> CoordinationCoordinator | None:
        with get_session() as session:
            stmt = select(CoordinationCoordinator).where(
                CoordinationCoordinator.coordination_id == coordination_id,
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationCoordinator.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationCoordinator.id.desc(),
            )
            return session.scalars(stmt).first()

    def get_by_id(self, coordinator_id: int) -> CoordinationCoordinator | None:
        with get_session() as session:
            return session.get(CoordinationCoordinator, coordinator_id)

    def find_by_participant(
        self,
        participant_id: int,
        *,
        active_only: bool = True,
    ) -> CoordinationCoordinator | None:
        with get_session() as session:
            stmt = select(CoordinationCoordinator).where(
                CoordinationCoordinator.participant_id == participant_id,
            )
            if active_only:
                stmt = stmt.where(CoordinationCoordinator.active == True)  # noqa: E712
            return session.scalars(stmt).first()

    def add(
        self,
        coordinator: CoordinationCoordinator,
    ) -> CoordinationCoordinator:
        with get_session() as session:
            session.add(coordinator)
            session.commit()
            session.refresh(coordinator)
            return coordinator

    def update(
        self,
        coordinator: CoordinationCoordinator,
    ) -> CoordinationCoordinator:
        with get_session() as session:
            coordinator = session.merge(coordinator)
            session.commit()
            session.refresh(coordinator)
            return coordinator
