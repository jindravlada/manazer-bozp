"""Služba bodů jednání."""

from __future__ import annotations

from moduly.schuzky.modely.meeting_agenda_item import MeetingAgendaItem
from moduly.schuzky.repository.meeting_agenda_item_repository import (
    MeetingAgendaItemRepository,
)


class MeetingAgendaItemService:
    def __init__(self) -> None:
        self.repository = MeetingAgendaItemRepository()

    def get_for_meeting(self, meeting_id: int) -> list[MeetingAgendaItem]:
        return self.repository.get_for_meeting(meeting_id)

    def item_to_dict(self, item: MeetingAgendaItem) -> dict:
        return {
            "id": item.id,
            "meeting_id": item.meeting_id,
            "display_order": int(item.display_order or 0),
            "title": item.title or "",
            "moje_sdeleni": getattr(item, "moje_sdeleni", None) or "",
            "prubeh_jednani": getattr(item, "prubeh_jednani", None) or "",
            "zaver": getattr(item, "zaver", None) or "",
        }

    def save_items(self, meeting_id: int, items: list[dict]) -> list[MeetingAgendaItem]:
        normalized = self._normalize_items(items)
        self.repository.delete_for_meeting(meeting_id)

        saved: list[MeetingAgendaItem] = []
        for index, data in enumerate(normalized):
            item = MeetingAgendaItem(
                meeting_id=int(meeting_id),
                display_order=int(data.get("display_order", (index + 1) * 10)),
                title=(data.get("title") or "").strip(),
                moje_sdeleni=data.get("moje_sdeleni") or "",
                prubeh_jednani=data.get("prubeh_jednani") or "",
                zaver=data.get("zaver") or "",
            )
            saved.append(self.repository.add(item))
        return saved

    def _normalize_items(self, items: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, raw in enumerate(items or []):
            normalized.append(
                {
                    "title": str(raw.get("title") or "").strip(),
                    "moje_sdeleni": str(raw.get("moje_sdeleni") or ""),
                    "prubeh_jednani": str(raw.get("prubeh_jednani") or ""),
                    "zaver": str(raw.get("zaver") or ""),
                    "display_order": (index + 1) * 10,
                }
            )
        return normalized


meeting_agenda_item_service = MeetingAgendaItemService()
