from moduly.nastaveni.modely.responsibility_role import ResponsibilityRole
from moduly.nastaveni.repository.responsibility_role_repository import ResponsibilityRoleRepository


class ResponsibilityRoleService:
    def __init__(self):
        self.repository = ResponsibilityRoleRepository()

    def get_all(self, include_inactive: bool = False) -> list[ResponsibilityRole]:
        return self.repository.get_all(include_inactive=include_inactive)

    def get_by_id(self, role_id: int | None) -> ResponsibilityRole | None:
        if not role_id:
            return None
        return self.repository.get_by_id(role_id)

    def create_role(
        self,
        *,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> ResponsibilityRole:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Název role je povinný.")

        role = ResponsibilityRole(
            name=normalized_name,
            description=description.strip(),
            active=active,
        )
        return self.repository.add(role)

    def update_role(
        self,
        role_id: int,
        *,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> ResponsibilityRole | None:
        role = self.repository.get_by_id(role_id)
        if role is None:
            return None

        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Název role je povinný.")

        role.name = normalized_name
        role.description = description.strip()
        role.active = active
        return self.repository.update(role)

    def activate(self, role_id: int) -> bool:
        return self.repository.activate(role_id)

    def deactivate(self, role_id: int) -> bool:
        return self.repository.deactivate(role_id)

    def display_name(self, role_id: int | None) -> str:
        role = self.get_by_id(role_id)
        return role.name if role else ""


responsibility_role_service = ResponsibilityRoleService()
