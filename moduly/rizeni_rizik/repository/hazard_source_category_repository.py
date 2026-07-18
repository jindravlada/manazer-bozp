from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_source_category import HazardSourceCategory


class HazardSourceCategoryRepository:
    def get_all(self, *, include_inactive: bool = False) -> list[HazardSourceCategory]:
        with get_session() as session:
            stmt = select(HazardSourceCategory)
            if not include_inactive:
                stmt = stmt.where(HazardSourceCategory.active.is_(True))
            stmt = stmt.order_by(
                HazardSourceCategory.sort_order,
                HazardSourceCategory.name,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, category_id: int) -> HazardSourceCategory | None:
        with get_session() as session:
            return session.get(HazardSourceCategory, category_id)

    def get_by_code(self, code: str) -> HazardSourceCategory | None:
        if not code:
            return None
        with get_session() as session:
            stmt = select(HazardSourceCategory).where(HazardSourceCategory.code == code)
            return session.scalar(stmt)

    def add(self, category: HazardSourceCategory) -> HazardSourceCategory:
        with get_session() as session:
            session.add(category)
            session.commit()
            session.refresh(category)
            return category

    def update(self, category: HazardSourceCategory) -> HazardSourceCategory:
        with get_session() as session:
            category = session.merge(category)
            session.commit()
            session.refresh(category)
            return category

    def activate(self, category_id: int) -> bool:
        return self._set_active(category_id, True)

    def deactivate(self, category_id: int) -> bool:
        return self._set_active(category_id, False)

    def _set_active(self, category_id: int, active: bool) -> bool:
        with get_session() as session:
            category = session.get(HazardSourceCategory, category_id)
            if category is None:
                return False
            category.active = active
            session.commit()
            return True

    def next_sort_order(self) -> int:
        with get_session() as session:
            stmt = select(HazardSourceCategory.sort_order).order_by(
                HazardSourceCategory.sort_order.desc(),
            )
            current = session.scalar(stmt)
            return (current or 0) + 1

    def count_all(self) -> int:
        with get_session() as session:
            return int(
                session.scalar(select(func.count()).select_from(HazardSourceCategory)) or 0
            )
