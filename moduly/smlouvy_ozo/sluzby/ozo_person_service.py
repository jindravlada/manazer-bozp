"""Služba údajů odborně způsobilé osoby."""

from __future__ import annotations

from datetime import date, datetime

from moduly.smlouvy_ozo.constants import format_ozo_display_name
from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson
from moduly.smlouvy_ozo.repository.ozo_person_repository import OzoPersonRepository


class OzoPersonService:
    def __init__(self, repository: OzoPersonRepository | None = None):
        self.repository = repository or OzoPersonRepository()

    def get(self) -> OzoPerson | None:
        return self.repository.get()

    def get_or_empty(self) -> OzoPerson:
        person = self.repository.get()
        if person is not None:
            return person
        return OzoPerson()

    def save(
        self,
        *,
        title_before: str = "",
        first_name: str = "",
        last_name: str = "",
        title_after: str = "",
        residence_address: str = "",
        exam_date: date | None = None,
        certificate_number: str = "",
        certificate_valid_to: date | None = None,
        note: str = "",
    ) -> OzoPerson:
        person = self.repository.get()
        if person is None:
            person = OzoPerson()
        person.title_before = (title_before or "").strip()
        person.first_name = (first_name or "").strip()
        person.last_name = (last_name or "").strip()
        person.title_after = (title_after or "").strip()
        person.residence_address = (residence_address or "").strip()
        person.exam_date = exam_date
        person.certificate_number = (certificate_number or "").strip()
        person.certificate_valid_to = certificate_valid_to
        person.note = (note or "").strip()
        person.updated_at = datetime.now()
        return self.repository.save(person)

    def missing_for_list_output(self, person: OzoPerson | None = None) -> list[str]:
        """Povinné pro chronologický seznam: jméno, příjmení, číslo osvědčení."""
        person = person if person is not None else self.get()
        missing: list[str] = []
        if person is None or not (person.first_name or "").strip():
            missing.append("Jméno")
        if person is None or not (person.last_name or "").strip():
            missing.append("Příjmení")
        if person is None or not (person.certificate_number or "").strip():
            missing.append("Číslo osvědčení")
        return missing

    def full_name(self, person: OzoPerson | None = None) -> str:
        person = person if person is not None else self.get()
        if person is None:
            return ""
        return format_ozo_display_name(
            getattr(person, "title_before", "") or "",
            person.first_name or "",
            person.last_name or "",
            getattr(person, "title_after", "") or "",
        )


ozo_person_service = OzoPersonService()
