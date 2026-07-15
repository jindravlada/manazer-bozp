from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted
from moduly.rizeni_rizik.modely.hazard_library_template_item import HazardLibraryTemplateItem


class HazardLibraryTemplateItemRepository:
    def get_for_template(
        self,
        template_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateItem]:
        with get_session() as session:
            stmt = select(HazardLibraryTemplateItem).where(
                HazardLibraryTemplateItem.template_id == template_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardLibraryTemplateItem.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardLibraryTemplateItem.category,
                HazardLibraryTemplateItem.sort_order,
                HazardLibraryTemplateItem.name,
                HazardLibraryTemplateItem.id,
            )
            items = list(session.scalars(stmt))
        return czech_sorted(
            items,
            key=lambda item: (item.category, item.sort_order, item.name),
        )

    def get_by_id(self, item_id: int) -> HazardLibraryTemplateItem | None:
        with get_session() as session:
            return session.get(HazardLibraryTemplateItem, item_id)

    def add(self, item: HazardLibraryTemplateItem) -> HazardLibraryTemplateItem:
        with get_session() as session:
            session.add(item)
            session.commit()
            session.refresh(item)
            return item

    def update(self, item: HazardLibraryTemplateItem) -> HazardLibraryTemplateItem:
        with get_session() as session:
            item = session.merge(item)
            session.commit()
            session.refresh(item)
            return item

    def next_sort_order(self, template_id: int, category: str) -> int:
        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplateItem.sort_order)
                .where(
                    HazardLibraryTemplateItem.template_id == template_id,
                    HazardLibraryTemplateItem.category == category,
                )
                .order_by(HazardLibraryTemplateItem.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1
