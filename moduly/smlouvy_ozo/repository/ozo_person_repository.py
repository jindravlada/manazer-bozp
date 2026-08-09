"""Persistence údajů OZO (jeden záznam)."""

from __future__ import annotations

from sqlalchemy import select

from core.database.session import get_session
from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson


class OzoPersonRepository:
    def get(self) -> OzoPerson | None:
        with get_session() as session:
            stmt = select(OzoPerson).limit(1)
            return session.scalars(stmt).first()

    def save(self, person: OzoPerson) -> OzoPerson:
        with get_session() as session:
            person = session.merge(person)
            session.commit()
            session.refresh(person)
            return person
