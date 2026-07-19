"""Služba míst výkonu práce koordinace (COORD-006)."""

from __future__ import annotations

from datetime import datetime

from moduly.koordinace_bozp.modely.coordination_workplace import CoordinationWorkplace
from moduly.koordinace_bozp.repository.coordination_workplace_repository import (
    CoordinationWorkplaceRepository,
)
from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
    WORKPLACE_ITEM_TYPE_WORKPLACE,
    WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)


class CoordinationWorkplaceError(ValueError):
    pass


class CoordinationWorkplaceService:
    def __init__(self) -> None:
        self.repository = CoordinationWorkplaceRepository()

    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationWorkplace]:
        return self.repository.list_for_coordination(
            coordination_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, workplace_link_id: int | None) -> CoordinationWorkplace | None:
        if not workplace_link_id:
            return None
        return self.repository.get_by_id(workplace_link_id)

    def get_operations(self, *, include_inactive: bool = False):
        return hazard_identification_service.get_active_operations(
            include_inactive=include_inactive,
        )

    def get_workplaces_for_operation(
        self,
        operation_id: int | None,
        *,
        include_inactive: bool = False,
    ):
        return hazard_identification_service.get_workplaces_for_operation(
            operation_id,
            include_inactive=include_inactive,
        )

    def get_parts_for_workplace(
        self,
        workplace_id: int | None,
        *,
        include_inactive: bool = False,
    ):
        return hazard_identification_service.get_workplace_parts_for_workplace(
            workplace_id,
            include_inactive=include_inactive,
        )

    def workplace_display_names(
        self,
        item: CoordinationWorkplace,
    ) -> tuple[str, str, str]:
        operation = settings_service.get_workplace_by_id(item.operation_id)
        workplace = (
            settings_service.get_workplace_by_id(item.workplace_id)
            if item.workplace_id
            else None
        )
        part = (
            settings_service.get_workplace_by_id(item.workplace_part_id)
            if item.workplace_part_id
            else None
        )
        return (
            (operation.name if operation else "") or "",
            (workplace.name if workplace else "") or "",
            (part.name if part else "") or "",
        )

    def add(
        self,
        coordination_id: int,
        *,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        note: str = "",
        active: bool = True,
    ) -> CoordinationWorkplace:
        operation_id, workplace_id, workplace_part_id = self._validate_selection(
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )
        self._ensure_unique(
            coordination_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )
        item = CoordinationWorkplace(
            coordination_id=coordination_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            note=(note or "").strip(),
            active=active,
            sort_order=self.repository.next_sort_order(coordination_id),
        )
        return self.repository.add(item)

    def update(
        self,
        workplace_link_id: int,
        *,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        note: str = "",
    ) -> CoordinationWorkplace | None:
        item = self.repository.get_by_id(workplace_link_id)
        if item is None:
            return None
        operation_id, workplace_id, workplace_part_id = self._validate_selection(
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )
        self._ensure_unique(
            item.coordination_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            exclude_id=item.id,
        )
        item.operation_id = operation_id
        item.workplace_id = workplace_id
        item.workplace_part_id = workplace_part_id
        item.note = (note or "").strip()
        item.updated_at = datetime.now()
        return self.repository.update(item)

    def activate(self, workplace_link_id: int) -> bool:
        item = self.repository.get_by_id(workplace_link_id)
        if item is None:
            return False
        self._ensure_unique(
            item.coordination_id,
            operation_id=item.operation_id,
            workplace_id=item.workplace_id,
            workplace_part_id=item.workplace_part_id,
            exclude_id=item.id,
            active_only=True,
        )
        item.active = True
        item.updated_at = datetime.now()
        self.repository.update(item)
        return True

    def deactivate(self, workplace_link_id: int) -> bool:
        item = self.repository.get_by_id(workplace_link_id)
        if item is None:
            return False
        item.active = False
        item.updated_at = datetime.now()
        self.repository.update(item)
        return True

    def _validate_selection(
        self,
        *,
        operation_id: int | None,
        workplace_id: int | None,
        workplace_part_id: int | None,
    ) -> tuple[int, int | None, int | None]:
        if not operation_id:
            raise CoordinationWorkplaceError("Provoz je povinný.")

        operation = settings_service.get_workplace_by_id(operation_id)
        if operation is None or operation.item_type != WORKPLACE_ITEM_TYPE_OPERATION:
            raise CoordinationWorkplaceError("Vyberte platný provoz.")

        normalized_workplace = workplace_id or None
        normalized_part = workplace_part_id or None

        if normalized_part is not None and normalized_workplace is None:
            raise CoordinationWorkplaceError(
                "Část pracoviště lze vybrat jen spolu s pracovištěm."
            )

        if normalized_workplace is not None:
            workplace = settings_service.get_workplace_by_id(normalized_workplace)
            if workplace is None or workplace.item_type != WORKPLACE_ITEM_TYPE_WORKPLACE:
                raise CoordinationWorkplaceError("Vyberte platné pracoviště.")
            if workplace.parent_id != operation_id:
                raise CoordinationWorkplaceError(
                    "Pracoviště nepatří pod vybraný provoz."
                )

        if normalized_part is not None:
            part = settings_service.get_workplace_by_id(normalized_part)
            if part is None or part.item_type != WORKPLACE_ITEM_TYPE_WORKPLACE_PART:
                raise CoordinationWorkplaceError("Vyberte platnou část pracoviště.")
            if part.parent_id != normalized_workplace:
                raise CoordinationWorkplaceError(
                    "Část pracoviště nepatří pod vybrané pracoviště."
                )

        return int(operation_id), normalized_workplace, normalized_part

    def _ensure_unique(
        self,
        coordination_id: int,
        *,
        operation_id: int,
        workplace_id: int | None,
        workplace_part_id: int | None,
        exclude_id: int | None = None,
        active_only: bool = False,
    ) -> None:
        for item in self.repository.list_for_coordination(
            coordination_id,
            include_inactive=not active_only,
        ):
            if exclude_id is not None and item.id == exclude_id:
                continue
            if active_only and not item.active:
                continue
            if (
                item.operation_id == operation_id
                and (item.workplace_id or None) == (workplace_id or None)
                and (item.workplace_part_id or None) == (workplace_part_id or None)
            ):
                raise CoordinationWorkplaceError(
                    "Stejné místo výkonu práce je u této koordinace již evidováno."
                )


coordination_workplace_service = CoordinationWorkplaceService()
