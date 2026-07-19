"""Služba číselníku profesí a vazeb na ohrožené skupiny (PBP-5c)."""

from __future__ import annotations

from datetime import datetime

from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.rizeni_rizik.modely.profession import Profession
from moduly.rizeni_rizik.repository.profession_exposed_group_repository import (
    ProfessionExposedGroupRepository,
)
from moduly.rizeni_rizik.repository.profession_repository import ProfessionRepository


class ProfessionError(ValueError):
    pass


def normalize_profession_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


class ProfessionService:
    def __init__(self) -> None:
        self.repository = ProfessionRepository()
        self.groups_repository = ProfessionExposedGroupRepository()

    def get_all(self, include_inactive: bool = False) -> list[Profession]:
        return self.repository.get_all(include_inactive=include_inactive)

    def get_active_all(self) -> list[Profession]:
        return self.repository.get_all(include_inactive=False)

    def get_by_id(self, profession_id: int | None) -> Profession | None:
        if not profession_id:
            return None
        return self.repository.get_by_id(profession_id)

    def display_name(self, profession_id: int | None) -> str:
        profession = self.get_by_id(profession_id)
        return profession.name if profession else ""

    def get_group_ids(self, profession_id: int) -> list[int]:
        return self.groups_repository.list_group_ids(profession_id)

    def get_active_exposed_group_ids(self, profession_id: int) -> list[int]:
        """Aktivní ohrožené skupiny přiřazené k profesi (pro generování PBP)."""
        active_ids: list[int] = []
        for group_id in self.get_group_ids(profession_id):
            group = exposed_group_service.get_by_id(group_id)
            if group is not None and group.active:
                active_ids.append(group_id)
        return active_ids

    def create_profession(
        self,
        *,
        name: str,
        note: str = "",
        active: bool = True,
        sort_order: int | None = None,
        exposed_group_ids: list[int] | None = None,
    ) -> Profession:
        normalized_name = self._validate_name(name)
        if active:
            self._ensure_unique_active_name(normalized_name)

        profession = Profession(
            name=normalized_name,
            note=note.strip(),
            active=active,
            sort_order=(
                sort_order
                if sort_order is not None
                else self.repository.next_sort_order()
            ),
        )
        created = self.repository.add(profession)
        self.groups_repository.replace_groups(created.id, exposed_group_ids or [])
        return created

    def update_profession(
        self,
        profession_id: int,
        *,
        name: str,
        note: str = "",
        active: bool = True,
        sort_order: int | None = None,
        exposed_group_ids: list[int] | None = None,
    ) -> Profession | None:
        profession = self.repository.get_by_id(profession_id)
        if profession is None:
            return None

        normalized_name = self._validate_name(name)
        if active:
            self._ensure_unique_active_name(
                normalized_name,
                exclude_profession_id=profession_id,
            )

        profession.name = normalized_name
        profession.note = note.strip()
        profession.active = active
        if sort_order is not None:
            profession.sort_order = sort_order
        profession.updated_at = datetime.now()
        updated = self.repository.update(profession)
        if exposed_group_ids is not None:
            self.groups_repository.replace_groups(profession_id, exposed_group_ids)
        return updated

    def set_exposed_groups(self, profession_id: int, group_ids: list[int]) -> None:
        if self.repository.get_by_id(profession_id) is None:
            raise ProfessionError("Profese nebyla nalezena.")
        self.groups_repository.replace_groups(profession_id, group_ids)

    def activate(self, profession_id: int) -> bool:
        profession = self.repository.get_by_id(profession_id)
        if profession is None:
            return False
        self._ensure_unique_active_name(
            profession.name,
            exclude_profession_id=profession_id,
        )
        return self.repository.activate(profession_id)

    def deactivate(self, profession_id: int) -> bool:
        return self.repository.deactivate(profession_id)

    def _validate_name(self, name: str) -> str:
        normalized_name = " ".join(name.strip().split())
        if not normalized_name:
            raise ProfessionError("Název profese je povinný.")
        return normalized_name

    def _ensure_unique_active_name(
        self,
        name: str,
        *,
        exclude_profession_id: int | None = None,
    ) -> None:
        normalized = normalize_profession_name(name)
        for profession in self.repository.get_all(include_inactive=False):
            if profession.id == exclude_profession_id:
                continue
            if normalize_profession_name(profession.name) == normalized:
                raise ProfessionError(
                    f"Aktivní profese „{profession.name}“ již existuje."
                )


profession_service = ProfessionService()
