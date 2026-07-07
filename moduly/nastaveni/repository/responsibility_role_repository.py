from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted
from moduly.nastaveni.modely.responsibility_role import ResponsibilityRole


class ResponsibilityRoleRepository:
    def get_all(self, include_inactive: bool = False) -> list[ResponsibilityRole]:
        with get_session() as session:
            stmt = select(ResponsibilityRole)
            if not include_inactive:
                stmt = stmt.where(ResponsibilityRole.active == True)  # noqa: E712
            roles = list(session.scalars(stmt))

        return czech_sorted(roles, key=lambda role: role.name)

    def get_by_id(self, role_id: int) -> ResponsibilityRole | None:
        with get_session() as session:
            return session.get(ResponsibilityRole, role_id)

    def add(self, role: ResponsibilityRole) -> ResponsibilityRole:
        with get_session() as session:
            session.add(role)
            session.commit()
            session.refresh(role)
            return role

    def update(self, role: ResponsibilityRole) -> ResponsibilityRole:
        with get_session() as session:
            role = session.merge(role)
            session.commit()
            session.refresh(role)
            return role

    def activate(self, role_id: int) -> bool:
        return self._set_active(role_id, True)

    def deactivate(self, role_id: int) -> bool:
        return self._set_active(role_id, False)

    def _set_active(self, role_id: int, active: bool) -> bool:
        with get_session() as session:
            role = session.get(ResponsibilityRole, role_id)
            if role is None:
                return False
            role.active = active
            session.commit()
            return True
