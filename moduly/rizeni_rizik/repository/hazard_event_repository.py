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
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem

        with get_session() as session:
            stmt = (
                select(HazardEvent)
                .join(
                    HazardInventoryItem,
                    HazardEvent.inventory_item_id == HazardInventoryItem.id,
                )
                .where(
                    HazardInventoryItem.hazard_identification_id == hazard_identification_id
                )
            )
            if not include_inactive:
                stmt = stmt.where(HazardEvent.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardEvent.inventory_item_id,
                HazardEvent.sort_order,
                HazardEvent.name,
                HazardEvent.id,
            )
            return list(session.scalars(stmt))

    def get_for_inventory_item(
        self,
        inventory_item_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardEvent]:
        with get_session() as session:
            stmt = select(HazardEvent).where(
                HazardEvent.inventory_item_id == inventory_item_id
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

    def count_active_for_inventory_item(self, inventory_item_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(HazardEvent)
                .where(
                    HazardEvent.inventory_item_id == inventory_item_id,
                    HazardEvent.active == True,  # noqa: E712
                )
            )
            return int(session.scalar(stmt) or 0)

    def next_sort_order(self, inventory_item_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(HazardEvent.sort_order)
                .where(HazardEvent.inventory_item_id == inventory_item_id)
                .order_by(HazardEvent.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1
