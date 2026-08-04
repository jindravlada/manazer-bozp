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

    def get_by_id(self, item_id: int) -> MeetingAgendaItem | None:
        with get_session() as session:
            return session.get(MeetingAgendaItem, int(item_id))

    def delete_for_meeting(self, meeting_id: int) -> int:
        with get_session() as session:
            result = session.execute(
                delete(MeetingAgendaItem).where(
                    MeetingAgendaItem.meeting_id == int(meeting_id)
                )
            )
            session.commit()
            return int(result.rowcount or 0)

    def delete_by_id(self, item_id: int) -> None:
        with get_session() as session:
            item = session.get(MeetingAgendaItem, int(item_id))
            if item is not None:
                session.delete(item)
                session.commit()

    def add(self, item: MeetingAgendaItem) -> MeetingAgendaItem:
        with get_session() as session:
            session.add(item)
            session.commit()
            session.refresh(item)
            return item

    def update(self, item: MeetingAgendaItem) -> MeetingAgendaItem:
        with get_session() as session:
            item = session.merge(item)
            session.commit()
            session.refresh(item)
            return item
