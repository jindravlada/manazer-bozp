from sqlalchemy import select

from core.database.session import get_session
from moduly.kniha_urazu.modely.accident import Accident


class AccidentRepository:
    def get_all(self) -> list[Accident]:
        with get_session() as session:
            stmt = select(Accident).order_by(Accident.year.desc(), Accident.id.desc())
            return list(session.scalars(stmt))

    def get_by_id(self, accident_id: int) -> Accident | None:
        with get_session() as session:
            return session.get(Accident, accident_id)

    def add(self, accident: Accident) -> Accident:
        with get_session() as session:
            session.add(accident)
            session.commit()
            session.refresh(accident)
            return accident

    def update(self, accident: Accident) -> Accident:
        with get_session() as session:
            accident = session.merge(accident)
            session.commit()
            session.refresh(accident)
            return accident
