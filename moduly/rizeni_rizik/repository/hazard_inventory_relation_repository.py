from sqlalchemy import select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_inventory_relation import HazardInventoryRelation


class HazardInventoryRelationRepository:
    def get_for_source_item(
        self,
        source_item_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardInventoryRelation]:
        with get_session() as session:
            stmt = select(HazardInventoryRelation).where(
                HazardInventoryRelation.source_item_id == source_item_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardInventoryRelation.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardInventoryRelation.relation_type,
                HazardInventoryRelation.id,
            )
            return list(session.scalars(stmt))

    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardInventoryRelation]:
        with get_session() as session:
            stmt = select(HazardInventoryRelation).where(
                HazardInventoryRelation.hazard_identification_id == hazard_identification_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardInventoryRelation.active == True)  # noqa: E712
            return list(session.scalars(stmt))

    def get_by_id(self, relation_id: int) -> HazardInventoryRelation | None:
        with get_session() as session:
            return session.get(HazardInventoryRelation, relation_id)

    def add(self, relation: HazardInventoryRelation) -> HazardInventoryRelation:
        with get_session() as session:
            session.add(relation)
            session.commit()
            session.refresh(relation)
            return relation

    def update(self, relation: HazardInventoryRelation) -> HazardInventoryRelation:
        with get_session() as session:
            relation = session.merge(relation)
            session.commit()
            session.refresh(relation)
            return relation

    def count_active_for_source(self, source_item_id: int) -> int:
        with get_session() as session:
            stmt = select(HazardInventoryRelation).where(
                HazardInventoryRelation.source_item_id == source_item_id,
                HazardInventoryRelation.active == True,  # noqa: E712
            )
            return len(list(session.scalars(stmt)))
