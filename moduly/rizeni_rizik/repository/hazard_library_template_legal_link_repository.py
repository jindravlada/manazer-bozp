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

    def list_active_template_ids_for_requirements(
        self,
        requirement_ids: list[int],
    ) -> list[int]:
        if not requirement_ids:
            return []
        from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate

        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplate.id)
                .join(
                    HazardLibraryTemplateLegalLink,
                    HazardLibraryTemplateLegalLink.template_id == HazardLibraryTemplate.id,
                )
                .where(
                    HazardLibraryTemplateLegalLink.legal_requirement_id.in_(requirement_ids),
                    HazardLibraryTemplateLegalLink.active == True,  # noqa: E712
                    HazardLibraryTemplate.active == True,  # noqa: E712
                )
                .distinct()
                .order_by(HazardLibraryTemplate.id)
            )
            return [int(template_id) for template_id in session.scalars(stmt)]

    def list_active_template_ids_for_documents(
        self,
        document_ids: list[int],
    ) -> list[int]:
        if not document_ids:
            return []
        from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate

        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplate.id)
                .join(
                    HazardLibraryTemplateLegalLink,
                    HazardLibraryTemplateLegalLink.template_id == HazardLibraryTemplate.id,
                )
                .where(
                    HazardLibraryTemplateLegalLink.legal_document_id.in_(document_ids),
                    HazardLibraryTemplateLegalLink.active == True,  # noqa: E712
                    HazardLibraryTemplate.active == True,  # noqa: E712
                )
                .distinct()
                .order_by(HazardLibraryTemplate.id)
            )
            return [int(template_id) for template_id in session.scalars(stmt)]
