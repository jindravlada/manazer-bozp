from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_library_template_event import HazardLibraryTemplateEvent


class HazardLibraryTemplateEventRepository:
    def get_for_template_item(
        self,
        template_item_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateEvent]:
        with get_session() as session:
            stmt = select(HazardLibraryTemplateEvent).where(
                HazardLibraryTemplateEvent.template_item_id == template_item_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardLibraryTemplateEvent.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardLibraryTemplateEvent.sort_order,
                HazardLibraryTemplateEvent.name,
                HazardLibraryTemplateEvent.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, event_id: int) -> HazardLibraryTemplateEvent | None:
        with get_session() as session:
            return session.get(HazardLibraryTemplateEvent, event_id)

    def add(self, event: HazardLibraryTemplateEvent) -> HazardLibraryTemplateEvent:
        with get_session() as session:
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    def update(self, event: HazardLibraryTemplateEvent) -> HazardLibraryTemplateEvent:
        with get_session() as session:
            event = session.merge(event)
            session.commit()
            session.refresh(event)
            return event

    def count_active_for_template_item(self, template_item_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(HazardLibraryTemplateEvent)
                .where(
                    HazardLibraryTemplateEvent.template_item_id == template_item_id,
                    HazardLibraryTemplateEvent.active == True,  # noqa: E712
                )
            )
            return int(session.scalar(stmt) or 0)

    def next_sort_order(self, template_item_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplateEvent.sort_order)
                .where(HazardLibraryTemplateEvent.template_item_id == template_item_id)
                .order_by(HazardLibraryTemplateEvent.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1
