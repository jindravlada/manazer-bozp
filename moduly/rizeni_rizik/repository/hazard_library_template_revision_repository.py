from sqlalchemy import select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
    HazardLibraryTemplateRevision,
)


class HazardLibraryTemplateRevisionRepository:
    def add(self, revision: HazardLibraryTemplateRevision) -> HazardLibraryTemplateRevision:
        with get_session() as session:
            session.add(revision)
            session.commit()
            session.refresh(revision)
            return revision

    def get_for_template(self, template_id: int) -> list[HazardLibraryTemplateRevision]:
        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplateRevision)
                .where(HazardLibraryTemplateRevision.template_id == template_id)
                .order_by(
                    HazardLibraryTemplateRevision.revision_number.desc(),
                    HazardLibraryTemplateRevision.created_at.desc(),
                )
            )
            return list(session.scalars(stmt))
