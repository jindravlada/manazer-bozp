from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
    HazardLibraryTemplateLegalLink,
)


class HazardLibraryTemplateLegalLinkRepository:
    def get_for_template(
        self,
        template_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateLegalLink]:
        with get_session() as session:
            stmt = select(HazardLibraryTemplateLegalLink).where(
                HazardLibraryTemplateLegalLink.template_id == template_id,
            )
            if not include_inactive:
                stmt = stmt.where(HazardLibraryTemplateLegalLink.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardLibraryTemplateLegalLink.sort_order,
                HazardLibraryTemplateLegalLink.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, link_id: int) -> HazardLibraryTemplateLegalLink | None:
        with get_session() as session:
            return session.get(HazardLibraryTemplateLegalLink, link_id)

    def add(self, link: HazardLibraryTemplateLegalLink) -> HazardLibraryTemplateLegalLink:
        with get_session() as session:
            session.add(link)
            session.commit()
            session.refresh(link)
            return link

    def update(self, link: HazardLibraryTemplateLegalLink) -> HazardLibraryTemplateLegalLink:
        with get_session() as session:
            link = session.merge(link)
            session.commit()
            session.refresh(link)
            return link

    def next_sort_order(self, template_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplateLegalLink.sort_order)
                .where(HazardLibraryTemplateLegalLink.template_id == template_id)
                .order_by(HazardLibraryTemplateLegalLink.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1
