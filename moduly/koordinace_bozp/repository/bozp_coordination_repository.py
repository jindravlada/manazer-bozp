from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination


class BozpCoordinationRepository:
    def get_all(self, include_inactive: bool = False) -> list[BozpCoordination]:
        with get_session() as session:
            stmt = select(BozpCoordination)
            if not include_inactive:
                stmt = stmt.where(BozpCoordination.active == True)  # noqa: E712
            stmt = stmt.order_by(
                BozpCoordination.meeting_date.desc(),
                BozpCoordination.id.desc(),
            )
            return list(session.scalars(stmt))

    def get_by_id(self, coordination_id: int) -> BozpCoordination | None:
        with get_session() as session:
            return session.get(BozpCoordination, coordination_id)

    def add(self, coordination: BozpCoordination) -> BozpCoordination:
        with get_session() as session:
            session.add(coordination)
            session.commit()
            session.refresh(coordination)
            return coordination

    def update(self, coordination: BozpCoordination) -> BozpCoordination:
        with get_session() as session:
            coordination = session.merge(coordination)
            session.commit()
            session.refresh(coordination)
            return coordination

    def allocate_next_number(self, year: int | None = None) -> str:
        """Samostatná číselná řada modulu: RRRR-0001."""
        from datetime import datetime

        target_year = year or datetime.now().year
        prefix = f"{target_year}-"
        with get_session() as session:
            stmt = select(BozpCoordination.coordination_number).where(
                BozpCoordination.coordination_number.like(f"{prefix}%")
            )
            max_sequence = 0
            for number in session.scalars(stmt):
                if not number:
                    continue
                try:
                    _, suffix = number.split("-", 1)
                    max_sequence = max(max_sequence, int(suffix))
                except (ValueError, IndexError):
                    continue
            return f"{target_year}-{max_sequence + 1:04d}"
