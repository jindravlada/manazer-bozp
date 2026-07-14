from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_event import HazardEvent


class HazardEventRepository:
    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardEvent]:
        from moduly.rizeni_rizik.modely.identified_hazard import IdentifiedHazard

        with get_session() as session:
            stmt = (
                select(HazardEvent)
                .join(
                    IdentifiedHazard,
                    HazardEvent.identified_hazard_id == IdentifiedHazard.id,
                )
                .where(IdentifiedHazard.hazard_identification_id == hazard_identification_id)
            )
            if not include_inactive:
                stmt = stmt.where(HazardEvent.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardEvent.identified_hazard_id,
                HazardEvent.sort_order,
                HazardEvent.name,
                HazardEvent.id,
            )
            return list(session.scalars(stmt))

    def get_for_identified_hazard(
        self,
        identified_hazard_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardEvent]:
        with get_session() as session:
            stmt = select(HazardEvent).where(
                HazardEvent.identified_hazard_id == identified_hazard_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardEvent.active == True)  # noqa: E712
            stmt = stmt.order_by(HazardEvent.sort_order, HazardEvent.name, HazardEvent.id)
            return list(session.scalars(stmt))

    def get_by_id(self, event_id: int) -> HazardEvent | None:
        with get_session() as session:
            return session.get(HazardEvent, event_id)

    def add(self, event: HazardEvent) -> HazardEvent:
        with get_session() as session:
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    def update(self, event: HazardEvent) -> HazardEvent:
        with get_session() as session:
            event = session.merge(event)
            session.commit()
            session.refresh(event)
            return event

    def count_active_for_hazard(self, identified_hazard_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(HazardEvent)
                .where(
                    HazardEvent.identified_hazard_id == identified_hazard_id,
                    HazardEvent.active == True,  # noqa: E712
                )
            )
            return int(session.scalar(stmt) or 0)

    def next_sort_order(self, identified_hazard_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(HazardEvent.sort_order)
                .where(HazardEvent.identified_hazard_id == identified_hazard_id)
                .order_by(HazardEvent.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1
