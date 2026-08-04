from sqlalchemy import select

from core.database.session import get_session
from moduly.schuzky.modely.meeting import Meeting


class MeetingRepository:
    def get_all(self) -> list[Meeting]:
        with get_session() as session:
            stmt = select(Meeting).order_by(Meeting.starts_at.desc(), Meeting.id.desc())
            return list(session.scalars(stmt))

    def get_by_id(self, meeting_id: int) -> Meeting | None:
        with get_session() as session:
            return session.get(Meeting, meeting_id)

    def add(self, meeting: Meeting) -> Meeting:
        with get_session() as session:
            session.add(meeting)
            session.commit()
            session.refresh(meeting)
            return meeting

    def update(self, meeting: Meeting) -> Meeting:
        with get_session() as session:
            meeting = session.merge(meeting)
            session.commit()
            session.refresh(meeting)
            return meeting
