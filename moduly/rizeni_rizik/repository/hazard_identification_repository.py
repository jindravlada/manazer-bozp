from sqlalchemy import select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification


class HazardIdentificationRepository:
    def get_all(self, include_inactive: bool = False) -> list[HazardIdentification]:
        with get_session() as session:
            stmt = select(HazardIdentification)
            if not include_inactive:
                stmt = stmt.where(HazardIdentification.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardIdentification.started_at.desc(),
                HazardIdentification.id.desc(),
            )
            return list(session.scalars(stmt))

    def get_by_id(self, identification_id: int) -> HazardIdentification | None:
        with get_session() as session:
            return session.get(HazardIdentification, identification_id)

    def add(self, identification: HazardIdentification) -> HazardIdentification:
        with get_session() as session:
            session.add(identification)
            session.commit()
            session.refresh(identification)
            return identification

    def update(self, identification: HazardIdentification) -> HazardIdentification:
        with get_session() as session:
            identification = session.merge(identification)
            session.commit()
            session.refresh(identification)
            return identification
