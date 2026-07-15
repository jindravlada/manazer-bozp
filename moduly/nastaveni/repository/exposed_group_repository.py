from sqlalchemy import select

from core.database.session import get_session
from moduly.nastaveni.modely.exposed_group import ExposedGroup


class ExposedGroupRepository:
    def get_all(self, include_inactive: bool = False) -> list[ExposedGroup]:
        with get_session() as session:
            stmt = select(ExposedGroup)
            if not include_inactive:
                stmt = stmt.where(ExposedGroup.active == True)  # noqa: E712
            stmt = stmt.order_by(
                ExposedGroup.sort_order,
                ExposedGroup.name,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, group_id: int) -> ExposedGroup | None:
        with get_session() as session:
            return session.get(ExposedGroup, group_id)

    def add(self, group: ExposedGroup) -> ExposedGroup:
        with get_session() as session:
            session.add(group)
            session.commit()
            session.refresh(group)
            return group

    def update(self, group: ExposedGroup) -> ExposedGroup:
        with get_session() as session:
            group = session.merge(group)
            session.commit()
            session.refresh(group)
            return group

    def activate(self, group_id: int) -> bool:
        return self._set_active(group_id, True)

    def deactivate(self, group_id: int) -> bool:
        return self._set_active(group_id, False)

    def _set_active(self, group_id: int, active: bool) -> bool:
        with get_session() as session:
            group = session.get(ExposedGroup, group_id)
            if group is None:
                return False
            group.active = active
            session.commit()
            return True

    def next_sort_order(self) -> int:
        with get_session() as session:
            stmt = select(ExposedGroup.sort_order).order_by(ExposedGroup.sort_order.desc())
            current = session.scalar(stmt)
            return (current or 0) + 1
