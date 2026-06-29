from datetime import datetime

from moduly.nastaveni.modely.person import Person
from moduly.nastaveni.repository.person_repository import PersonRepository


class PersonService:
    def __init__(self):
        self.repository = PersonRepository()

    def get_all(self, include_inactive: bool = False) -> list[Person]:
        return self.repository.get_all(include_inactive=include_inactive)

    def get_by_id(self, person_id: int | None) -> Person | None:
        if not person_id:
            return None
        return self.repository.get_by_id(person_id)

    def create_person(
        self,
        title_before: str = "",
        first_name: str = "",
        last_name: str = "",
        title_after: str = "",
        organization: str = "",
        job_title: str = "",
        email: str = "",
        phone: str = "",
        note: str = "",
        active: bool = True,
        is_employee: bool = False,
    ) -> Person:
        self._validate_name(first_name, last_name)

        person = Person(
            title_before=title_before.strip(),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            title_after=title_after.strip(),
            organization=organization.strip(),
            job_title=job_title.strip(),
            email=email.strip(),
            phone=phone.strip(),
            note=note.strip(),
            active=active,
            is_employee=is_employee,
        )
        return self.repository.add(person)

    def update_person(
        self,
        person_id: int,
        title_before: str = "",
        first_name: str = "",
        last_name: str = "",
        title_after: str = "",
        organization: str = "",
        job_title: str = "",
        email: str = "",
        phone: str = "",
        note: str = "",
        active: bool = True,
        is_employee: bool = False,
    ) -> Person | None:
        person = self.repository.get_by_id(person_id)
        if person is None:
            return None

        self._validate_name(first_name, last_name)

        person.title_before = title_before.strip()
        person.first_name = first_name.strip()
        person.last_name = last_name.strip()
        person.title_after = title_after.strip()
        person.organization = organization.strip()
        person.job_title = job_title.strip()
        person.email = email.strip()
        person.phone = phone.strip()
        person.note = note.strip()
        person.active = active
        person.is_employee = is_employee
        person.updated_at = datetime.now()

        return self.repository.update(person)

    def activate(self, person_id: int) -> bool:
        return self.repository.activate(person_id)

    def deactivate(self, person_id: int) -> bool:
        return self.repository.deactivate(person_id)

    def display_name(self, person_id: int | None) -> str:
        person = self.get_by_id(person_id)
        return person.display_name if person else ""

    def _validate_name(self, first_name: str, last_name: str) -> None:
        if not first_name.strip() or not last_name.strip():
            raise ValueError("Jméno i příjmení jsou povinné.")


person_service = PersonService()
