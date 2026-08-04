from sqlalchemy import select

from core.database.session import get_session
from moduly.schuzky.modely.meeting_event_type import MeetingEventType


class MeetingEventTypeRepository:
    def get_all(self, include_inactive: bool = False) -> list[MeetingEventType]:
        with get_session() as session:
            stmt = select(MeetingEventType)
            if not include_inactive:
                stmt = stmt.where(MeetingEventType.active == True)  # noqa: E712
            stmt = stmt.order_by(
                MeetingEventType.sort_order,
                MeetingEventType.name,
            )
            return list(session.scalars(stmt))

    def get_by_name(self, name: str) -> MeetingEventType | None:
        normalized = (name or "").strip()
        if not normalized:
            return None
        with get_session() as session:
            stmt = select(MeetingEventType).where(MeetingEventType.name == normalized)
            return session.scalars(stmt).first()
