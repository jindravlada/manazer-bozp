from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted, worker_sort_key
from moduly.nastaveni.modely.person import Person


class PersonRepository:
    def get_all(self, include_inactive: bool = False) -> list[Person]:
        with get_session() as session:
            stmt = select(Person)
            if not include_inactive:
                stmt = stmt.where(Person.active == True)  # noqa: E712
            persons = list(session.scalars(stmt))

        return czech_sorted(persons, key=worker_sort_key)

    def get_by_id(self, person_id: int) -> Person | None:
        with get_session() as session:
            return session.get(Person, person_id)

    def add(self, person: Person) -> Person:
        with get_session() as session:
            session.add(person)
            session.commit()
            session.refresh(person)
            return person

    def update(self, person: Person) -> Person:
        with get_session() as session:
            person = session.merge(person)
            session.commit()
            session.refresh(person)
            return person

    def activate(self, person_id: int) -> bool:
        return self._set_active(person_id, True)

    def deactivate(self, person_id: int) -> bool:
        return self._set_active(person_id, False)

    def _set_active(self, person_id: int, active: bool) -> bool:
        with get_session() as session:
            person = session.get(Person, person_id)
            if person is None:
                return False

            person.active = active
            session.commit()
            return True
