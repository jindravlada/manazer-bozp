from sqlalchemy import select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.profession import Profession


class ProfessionRepository:
    def get_all(self, include_inactive: bool = False) -> list[Profession]:
        with get_session() as session:
            stmt = select(Profession)
            if not include_inactive:
                stmt = stmt.where(Profession.active == True)  # noqa: E712
            stmt = stmt.order_by(Profession.sort_order, Profession.name)
            return list(session.scalars(stmt))

    def get_by_id(self, profession_id: int) -> Profession | None:
        with get_session() as session:
            return session.get(Profession, profession_id)

    def add(self, profession: Profession) -> Profession:
        with get_session() as session:
            session.add(profession)
            session.commit()
            session.refresh(profession)
            return profession

    def update(self, profession: Profession) -> Profession:
        with get_session() as session:
            profession = session.merge(profession)
            session.commit()
            session.refresh(profession)
            return profession

    def activate(self, profession_id: int) -> bool:
        return self._set_active(profession_id, True)

    def deactivate(self, profession_id: int) -> bool:
        return self._set_active(profession_id, False)

    def _set_active(self, profession_id: int, active: bool) -> bool:
        with get_session() as session:
            profession = session.get(Profession, profession_id)
            if profession is None:
                return False
            profession.active = active
            session.commit()
            return True

    def next_sort_order(self) -> int:
        with get_session() as session:
            stmt = select(Profession.sort_order).order_by(Profession.sort_order.desc())
            current = session.scalar(stmt)
            return (current or 0) + 1
