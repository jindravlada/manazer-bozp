from datetime import date, datetime

from moduly.kontroly.modely.control import Control
from moduly.kontroly.repository.control_repository import ControlRepository
from moduly.nastaveni.sluzby.settings_service import settings_service


class ControlService:
    def __init__(self):
        self.repository = ControlRepository()

    def get_all(self):
        return self.repository.get_all()

    def get_by_id(self, control_id: int):
        return self.repository.get_by_id(control_id)

    def create_control(
        self,
        title: str,
        inspection_date: date | None = None,
        workplace_id: int | None = None,
        inspector_id: int | None = None,
        result: str = "",
        note: str = "",
        sd_reference: str = "",
        next_due_date: date | None = None,
    ) -> Control:
        control = Control(
            title=title,
            inspection_date=inspection_date,
            workplace_id=workplace_id,
            workplace_name=self._workplace_name(workplace_id),
            inspector_id=inspector_id,
            inspector_name=self._person_name(inspector_id),
            result=result,
            note=note,
            sd_reference=sd_reference,
            next_due_date=next_due_date,
        )
        return self.repository.add(control)

    def update_control(
        self,
        control_id: int,
        title: str,
        inspection_date: date | None = None,
        workplace_id: int | None = None,
        inspector_id: int | None = None,
        result: str = "",
        note: str = "",
        sd_reference: str = "",
        next_due_date: date | None = None,
    ) -> Control | None:
        control = self.repository.get_by_id(control_id)
        if control is None:
            return None

        control.title = title
        control.inspection_date = inspection_date
        control.workplace_id = workplace_id
        control.workplace_name = self._workplace_name(workplace_id)
        control.inspector_id = inspector_id
        control.inspector_name = self._person_name(inspector_id)
        control.result = result
        control.note = note
        control.sd_reference = sd_reference
        control.next_due_date = next_due_date
        control.updated_at = datetime.now()

        return self.repository.update(control)

    def _person_name(self, person_id: int | None) -> str:
        if not person_id:
            return ""

        person = settings_service.get_worker_by_id(person_id)
        return person.display_name if person else ""

    def _workplace_name(self, workplace_id: int | None) -> str:
        if not workplace_id:
            return ""

        workplace = settings_service.get_workplace_by_id(workplace_id)
        return workplace.name if workplace else ""


control_service = ControlService()
