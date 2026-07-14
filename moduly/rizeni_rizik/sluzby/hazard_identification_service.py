from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.rizeni_rizik.constants import DEFAULT_HAZARD_IDENTIFICATION_STATUS
from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
from moduly.rizeni_rizik.repository.hazard_identification_repository import (
    HazardIdentificationRepository,
)


class HazardIdentificationService:
    def __init__(self):
        self.repository = HazardIdentificationRepository()

    def get_all(self, include_inactive: bool = False) -> list[HazardIdentification]:
        return self.repository.get_all(include_inactive=include_inactive)

    def get_by_id(self, identification_id: int | None) -> HazardIdentification | None:
        if not identification_id:
            return None
        return self.repository.get_by_id(identification_id)

    def create_identification(
        self,
        *,
        title: str,
        operation_id: int | None = None,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        responsible_person_id: int | None = None,
        started_at=None,
        status: str = DEFAULT_HAZARD_IDENTIFICATION_STATUS,
        note: str = "",
        active: bool = True,
    ) -> HazardIdentification:
        identification = HazardIdentification(
            title=title.strip(),
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
        person = person_service.get_by_id(person_id)
        return person.display_name if person else ""


hazard_identification_service = HazardIdentificationService()
