from datetime import datetime

from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
    WORKPLACE_ITEM_TYPE_WORKPLACE,
    WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.rizeni_rizik.constants import (
    DEFAULT_HAZARD_IDENTIFICATION_STATUS,
    HAZARD_IDENTIFICATION_STATUSES,
)
from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
from moduly.rizeni_rizik.repository.hazard_identification_repository import (
    HazardIdentificationRepository,
)
from core.utils.czech_sort import czech_sorted


class HazardIdentificationError(ValueError):
    pass


class HazardIdentificationService:
    def __init__(self):
        self.repository = HazardIdentificationRepository()

    def get_all(self, include_inactive: bool = False) -> list[HazardIdentification]:
        return self.repository.get_all(include_inactive=include_inactive)

    def get_by_id(self, identification_id: int | None) -> HazardIdentification | None:
        if not identification_id:
            return None
        return self.repository.get_by_id(identification_id)

    def get_active_operations(self, *, include_inactive: bool = False) -> list:
        workplaces = settings_service.get_workplaces(include_inactive=include_inactive)
        operations = [
            workplace
            for workplace in workplaces
            if workplace.item_type == WORKPLACE_ITEM_TYPE_OPERATION
        ]
        return czech_sorted(operations, key=lambda item: item.name)

    def get_workplaces_for_operation(
        self,
        operation_id: int | None,
        *,
        include_inactive: bool = False,
    ) -> list:
        if not operation_id:
            return []
        workplaces = settings_service.get_workplaces(include_inactive=include_inactive)
        items = [
            workplace
            for workplace in workplaces
            if workplace.item_type == WORKPLACE_ITEM_TYPE_WORKPLACE
            and workplace.parent_id == operation_id
        ]
        return czech_sorted(items, key=lambda item: item.name)

    def get_workplace_parts_for_workplace(
        self,
        workplace_id: int | None,
        *,
        include_inactive: bool = False,
    ) -> list:
        if not workplace_id:
            return []
        workplaces = settings_service.get_workplaces(include_inactive=include_inactive)
        items = [
            workplace
            for workplace in workplaces
            if workplace.item_type == WORKPLACE_ITEM_TYPE_WORKPLACE_PART
            and workplace.parent_id == workplace_id
        ]
        return czech_sorted(items, key=lambda item: item.name)

    def validate_workplace_selection(
        self,
        *,
        operation_id: int | None,
        workplace_id: int | None,
        workplace_part_id: int | None = None,
    ) -> None:
        if not operation_id:
            raise HazardIdentificationError("Provoz je povinný.")

        operation = settings_service.get_workplace_by_id(operation_id)
        if operation is None or operation.item_type != WORKPLACE_ITEM_TYPE_OPERATION:
            raise HazardIdentificationError("Vyberte platný provoz.")

        if workplace_id is None:
            if workplace_part_id is not None:
                raise HazardIdentificationError(
                    "Část pracoviště nelze zvolit bez pracoviště.",
                )
            return

        workplace = settings_service.get_workplace_by_id(workplace_id)
        if workplace is None or workplace.item_type != WORKPLACE_ITEM_TYPE_WORKPLACE:
            raise HazardIdentificationError("Vyberte platné pracoviště.")
        if workplace.parent_id != operation_id:
            raise HazardIdentificationError("Pracoviště nepatří pod vybraný provoz.")

        if workplace_part_id is None:
            return

        workplace_part = settings_service.get_workplace_by_id(workplace_part_id)
        if workplace_part is None or workplace_part.item_type != WORKPLACE_ITEM_TYPE_WORKPLACE_PART:
            raise HazardIdentificationError("Vyberte platnou část pracoviště.")
        if workplace_part.parent_id != workplace_id:
            raise HazardIdentificationError("Část pracoviště nepatří pod vybrané pracoviště.")

    def create_identification(
        self,
        *,
        operation_id: int | None = None,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        responsible_person_id: int | None = None,
        started_at=None,
        status: str = DEFAULT_HAZARD_IDENTIFICATION_STATUS,
        note: str = "",
        active: bool = True,
    ) -> HazardIdentification:
        if status not in HAZARD_IDENTIFICATION_STATUSES:
            raise HazardIdentificationError("Neplatný stav identifikace.")

        self.validate_workplace_selection(
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )

        identification = HazardIdentification(
            identification_number=self.repository.allocate_next_number(),
            operation_id=operation_id,
            operation_name=self._workplace_name(operation_id),
            workplace_id=workplace_id,
            workplace_name=self._workplace_name(workplace_id),
            workplace_part_id=workplace_part_id,
            workplace_part_name=self._workplace_name(workplace_part_id),
            responsible_person_id=responsible_person_id,
            responsible_person_name=self._person_name(responsible_person_id),
            started_at=started_at,
            status=status,
            note=note.strip(),
            active=active,
        )
        return self.repository.add(identification)

    def update_identification(
        self,
        identification_id: int,
        **data,
    ) -> HazardIdentification | None:
        identification = self.repository.get_by_id(identification_id)
        if identification is None:
            return None

        operation_id = data.get("operation_id", identification.operation_id)
        workplace_id = data.get("workplace_id", identification.workplace_id)
        workplace_part_id = data.get("workplace_part_id", identification.workplace_part_id)
        status = data.get("status", identification.status)
        if status not in HAZARD_IDENTIFICATION_STATUSES:
            raise HazardIdentificationError("Neplatný stav identifikace.")

        self.validate_workplace_selection(
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )

        identification.operation_id = operation_id
        identification.operation_name = self._workplace_name(operation_id)
        identification.workplace_id = workplace_id
        identification.workplace_name = self._workplace_name(workplace_id)
        identification.workplace_part_id = workplace_part_id
        identification.workplace_part_name = self._workplace_name(workplace_part_id)
        identification.responsible_person_id = data.get(
            "responsible_person_id",
            identification.responsible_person_id,
        )
        identification.responsible_person_name = self._person_name(
            identification.responsible_person_id
        )
        identification.started_at = data.get("started_at", identification.started_at)
        identification.status = status
        identification.note = str(data.get("note", identification.note)).strip()
        if "active" in data:
            identification.active = bool(data["active"])
        identification.updated_at = datetime.now()
        return self.repository.update(identification)

    def activate(self, identification_id: int) -> bool:
        identification = self.repository.get_by_id(identification_id)
        if identification is None:
            return False
        identification.active = True
        identification.updated_at = datetime.now()
        self.repository.update(identification)
        return True

    def deactivate(self, identification_id: int) -> bool:
        identification = self.repository.get_by_id(identification_id)
        if identification is None:
            return False
        identification.active = False
        identification.updated_at = datetime.now()
        self.repository.update(identification)
        return True

    @staticmethod
    def _workplace_name(workplace_id: int | None) -> str:
        if not workplace_id:
            return ""
        workplace = settings_service.get_workplace_by_id(workplace_id)
        return workplace.name if workplace else ""

    @staticmethod
    def _person_name(person_id: int | None) -> str:
        if not person_id:
            return ""
        worker = settings_service.get_worker_by_id(person_id)
        return worker.display_name if worker else ""


hazard_identification_service = HazardIdentificationService()
