from sqlalchemy import select

from core.database.session import get_session
from moduly.schuzky.modely.meeting_template import MeetingTemplate


class MeetingTemplateRepository:
    def get_all(self) -> list[MeetingTemplate]:
        with get_session() as session:
            stmt = select(MeetingTemplate).order_by(
                MeetingTemplate.name.asc(),
                MeetingTemplate.id.asc(),
            )
            return list(session.scalars(stmt))

    def get_by_id(self, template_id: int) -> MeetingTemplate | None:
        with get_session() as session:
            return session.get(MeetingTemplate, template_id)

    def add(self, template: MeetingTemplate) -> MeetingTemplate:
        with get_session() as session:
            session.add(template)
            session.commit()
            session.refresh(template)
            return template

    def update(self, template: MeetingTemplate) -> MeetingTemplate:
        with get_session() as session:
            merged = session.merge(template)
            session.commit()
            session.refresh(merged)
            return merged

    def delete(self, template_id: int) -> bool:
        with get_session() as session:
            template = session.get(MeetingTemplate, template_id)
            if template is None:
                return False
            session.delete(template)
            session.commit()
            return True
