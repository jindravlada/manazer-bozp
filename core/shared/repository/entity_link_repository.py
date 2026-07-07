from sqlalchemy import delete, select

from core.database.session import get_session
from core.shared.modely.entity_link import EntityLink


class EntityLinkRepository:
    def list_for_source(
        self,
        source_type: str,
        source_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[EntityLink]:
        with get_session() as session:
            stmt = (
                select(EntityLink)
                .where(
                    EntityLink.source_type == source_type,
                    EntityLink.source_id == source_id,
                )
                .order_by(EntityLink.active.desc(), EntityLink.id)
            )
            if not include_inactive:
                stmt = stmt.where(EntityLink.active.is_(True))
            return list(session.scalars(stmt))

    def list_for_target(
        self,
        target_type: str,
        target_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[EntityLink]:
        with get_session() as session:
            stmt = (
                select(EntityLink)
                .where(
                    EntityLink.target_type == target_type,
                    EntityLink.target_id == target_id,
                )
                .order_by(EntityLink.active.desc(), EntityLink.id)
            )
            if not include_inactive:
                stmt = stmt.where(EntityLink.active.is_(True))
            return list(session.scalars(stmt))

    def list_between(
        self,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[EntityLink]:
        with get_session() as session:
            stmt = (
                select(EntityLink)
                .where(
                    EntityLink.source_type == source_type,
                    EntityLink.source_id == source_id,
                    EntityLink.target_type == target_type,
                    EntityLink.target_id == target_id,
                )
                .order_by(EntityLink.active.desc(), EntityLink.id)
            )
            if not include_inactive:
                stmt = stmt.where(EntityLink.active.is_(True))
            return list(session.scalars(stmt))

    def find_active_duplicate(
        self,
        *,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        link_type: str,
        exclude_id: int | None = None,
    ) -> EntityLink | None:
        with get_session() as session:
            stmt = (
                select(EntityLink)
                .where(
                    EntityLink.source_type == source_type,
                    EntityLink.source_id == source_id,
                    EntityLink.target_type == target_type,
                    EntityLink.target_id == target_id,
                    EntityLink.link_type == link_type,
                    EntityLink.active.is_(True),
                )
                .order_by(EntityLink.id.desc())
            )
            if exclude_id is not None:
                stmt = stmt.where(EntityLink.id != exclude_id)
            return session.scalars(stmt).first()

    def get_by_id(self, link_id: int) -> EntityLink | None:
        with get_session() as session:
            return session.get(EntityLink, link_id)

    def create(self, link: EntityLink) -> EntityLink:
        with get_session() as session:
            session.add(link)
            session.commit()
            session.refresh(link)
            return link

    def update(self, link: EntityLink) -> EntityLink:
        with get_session() as session:
            link = session.merge(link)
            session.commit()
            session.refresh(link)
            return link

    def delete(self, link_id: int) -> bool:
        with get_session() as session:
            link = session.get(EntityLink, link_id)
            if link is None:
                return False
            session.delete(link)
            session.commit()
            return True
