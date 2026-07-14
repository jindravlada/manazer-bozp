from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.identified_hazard import IdentifiedHazard


class IdentifiedHazardRepository:
    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[IdentifiedHazard]:
        with get_session() as session:
            stmt = select(IdentifiedHazard).where(
                IdentifiedHazard.hazard_identification_id == hazard_identification_id
            )
            if not include_inactive:
                stmt = stmt.where(IdentifiedHazard.active == True)  # noqa: E712
            stmt = stmt.order_by(
                IdentifiedHazard.inventory_item_id,
                IdentifiedHazard.name,
                IdentifiedHazard.id,
            )
            return list(session.scalars(stmt))

    def get_for_inventory_item(
        self,
        inventory_item_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[IdentifiedHazard]:
        with get_session() as session:
            stmt = select(IdentifiedHazard).where(
                IdentifiedHazard.inventory_item_id == inventory_item_id
            )
            if not include_inactive:
                stmt = stmt.where(IdentifiedHazard.active == True)  # noqa: E712
            stmt = stmt.order_by(IdentifiedHazard.name, IdentifiedHazard.id)
            return list(session.scalars(stmt))

    def get_by_id(self, hazard_id: int) -> IdentifiedHazard | None:
        with get_session() as session:
            return session.get(IdentifiedHazard, hazard_id)

    def add(self, hazard: IdentifiedHazard) -> IdentifiedHazard:
        with get_session() as session:
            session.add(hazard)
            session.commit()
            session.refresh(hazard)
            return hazard

    def update(self, hazard: IdentifiedHazard) -> IdentifiedHazard:
        with get_session() as session:
            hazard = session.merge(hazard)
            session.commit()
            session.refresh(hazard)
            return hazard

    def count_active_for_inventory_item(self, inventory_item_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(IdentifiedHazard)
                .where(
                    IdentifiedHazard.inventory_item_id == inventory_item_id,
                    IdentifiedHazard.active == True,  # noqa: E712
                )
            )
            return int(session.scalar(stmt) or 0)
