"""Repository bodů jednání."""

from __future__ import annotations

from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.schuzky.modely.meeting_agenda_item import MeetingAgendaItem


class MeetingAgendaItemRepository:
    def get_for_meeting(self, meeting_id: int) -> list[MeetingAgendaItem]:
        with get_session() as session:
            stmt = (
                select(MeetingAgendaItem)
                .where(MeetingAgendaItem.meeting_id == int(meeting_id))
                .order_by(MeetingAgendaItem.display_order, MeetingAgendaItem.id)
            )
            return list(session.scalars(stmt))

    def delete_for_meeting(self, meeting_id: int) -> int:
        with get_session() as session:
            result = session.execute(
                delete(MeetingAgendaItem).where(
                    MeetingAgendaItem.meeting_id == int(meeting_id)
                )
            )
            session.commit()
            return int(result.rowcount or 0)

    def add(self, item: MeetingAgendaItem) -> MeetingAgendaItem:
        with get_session() as session:
            session.add(item)
            session.commit()
            session.refresh(item)
            return item
