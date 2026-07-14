from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted
from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem


class HazardInventoryItemRepository:
    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardInventoryItem]:
        with get_session() as session:
            stmt = select(HazardInventoryItem).where(
                HazardInventoryItem.hazard_identification_id == hazard_identification_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardInventoryItem.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardInventoryItem.category,
                HazardInventoryItem.sort_order,
                HazardInventoryItem.name,
                HazardInventoryItem.id,
            )
            items = list(session.scalars(stmt))
        return czech_sorted(
            items,
            key=lambda item: (item.category, item.sort_order, item.name),
        )

    def get_by_id(self, item_id: int) -> HazardInventoryItem | None:
        with get_session() as session:
            return session.get(HazardInventoryItem, item_id)

    def add(self, item: HazardInventoryItem) -> HazardInventoryItem:
        with get_session() as session:
            session.add(item)
            session.commit()
            session.refresh(item)
            return item

    def update(self, item: HazardInventoryItem) -> HazardInventoryItem:
        with get_session() as session:
            item = session.merge(item)
            session.commit()
            session.refresh(item)
            return item

    def next_sort_order(self, hazard_identification_id: int, category: str) -> int:
        with get_session() as session:
            stmt = (
                select(HazardInventoryItem.sort_order)
                .where(
                    HazardInventoryItem.hazard_identification_id == hazard_identification_id,
                    HazardInventoryItem.category == category,
                )
                .order_by(HazardInventoryItem.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1
