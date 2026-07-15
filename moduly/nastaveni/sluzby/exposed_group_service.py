from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from moduly.nastaveni.modely.exposed_group import ExposedGroup
from moduly.nastaveni.repository.exposed_group_repository import ExposedGroupRepository


class ExposedGroupError(ValueError):
    pass


class ExposedGroupMatchKind(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    NONE = "none"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class ExposedGroupMatchResult:
    kind: ExposedGroupMatchKind
    groups: tuple[ExposedGroup, ...] = ()


def normalize_exposed_group_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


class ExposedGroupService:
    def __init__(self):
        self.repository = ExposedGroupRepository()

    def get_all(self, include_inactive: bool = False) -> list[ExposedGroup]:
        return self.repository.get_all(include_inactive=include_inactive)

    def get_active_all(self) -> list[ExposedGroup]:
        return self.repository.get_all(include_inactive=False)

    def get_by_id(self, group_id: int | None) -> ExposedGroup | None:
        if not group_id:
            return None
        return self.repository.get_by_id(group_id)

    def display_name(self, group_id: int | None) -> str:
        group = self.get_by_id(group_id)
        return group.name if group else ""

    def create_group(
        self,
        *,
        name: str,
        note: str = "",
        active: bool = True,
        sort_order: int | None = None,
    ) -> ExposedGroup:
        normalized_name = self._validate_name(name)
        if active:
            self._ensure_unique_active_name(normalized_name)

        group = ExposedGroup(
            name=normalized_name,
            note=note.strip(),
            active=active,
            sort_order=sort_order if sort_order is not None else self.repository.next_sort_order(),
        )
        return self.repository.add(group)

    def update_group(
        self,
        group_id: int,
        *,
        name: str,
        note: str = "",
        active: bool = True,
        sort_order: int | None = None,
    ) -> ExposedGroup | None:
        group = self.repository.get_by_id(group_id)
        if group is None:
            return None

        normalized_name = self._validate_name(name)
        if active:
            self._ensure_unique_active_name(normalized_name, exclude_group_id=group_id)

        group.name = normalized_name
        group.note = note.strip()
        group.active = active
        if sort_order is not None:
            group.sort_order = sort_order
        group.updated_at = datetime.now()
        return self.repository.update(group)

    def activate(self, group_id: int) -> bool:
        group = self.repository.get_by_id(group_id)
        if group is None:
            return False
        self._ensure_unique_active_name(group.name, exclude_group_id=group_id)
        return self.repository.activate(group_id)

    def deactivate(self, group_id: int) -> bool:
        return self.repository.deactivate(group_id)

    def find_matches(
        self,
        name: str,
        *,
        include_inactive: bool = True,
    ) -> list[ExposedGroup]:
        normalized = normalize_exposed_group_name(name)
        if not normalized:
            return []
        return [
            group
            for group in self.repository.get_all(include_inactive=include_inactive)
            if normalize_exposed_group_name(group.name) == normalized
        ]

    def classify_name(self, name: str) -> ExposedGroupMatchResult:
        matches = self.find_matches(name, include_inactive=True)
        if not matches:
            return ExposedGroupMatchResult(kind=ExposedGroupMatchKind.NONE)
        if len(matches) > 1:
            return ExposedGroupMatchResult(
                kind=ExposedGroupMatchKind.AMBIGUOUS,
                groups=tuple(matches),
            )
        group = matches[0]
        if group.active:
            return ExposedGroupMatchResult(
                kind=ExposedGroupMatchKind.ACTIVE,
                groups=(group,),
            )
        return ExposedGroupMatchResult(
            kind=ExposedGroupMatchKind.INACTIVE,
            groups=(group,),
        )

    def find_or_create_for_migration(self, name: str) -> ExposedGroup:
        """Pouze pro migraci dat – vytvoří aktivní položku, pokud shoda neexistuje."""
        normalized_name = self._validate_name(name)
        matches = self.find_matches(normalized_name, include_inactive=True)
        if matches:
            return matches[0]
        return self.create_group(name=normalized_name, active=True)

    def _validate_name(self, name: str) -> str:
        normalized_name = " ".join(name.strip().split())
        if not normalized_name:
            raise ExposedGroupError("Název ohrožené skupiny je povinný.")
        return normalized_name

    def _ensure_unique_active_name(
        self,
        name: str,
        *,
        exclude_group_id: int | None = None,
    ) -> None:
        normalized = normalize_exposed_group_name(name)
        for group in self.repository.get_all(include_inactive=False):
            if group.id == exclude_group_id:
                continue
            if normalize_exposed_group_name(group.name) == normalized:
                raise ExposedGroupError(
                    f"Aktivní ohrožená skupina „{group.name}“ již existuje."
                )


exposed_group_service = ExposedGroupService()
