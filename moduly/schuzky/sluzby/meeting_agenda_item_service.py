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

    def get_by_id(self, item_id: int) -> MeetingAgendaItem | None:
        return self.repository.get_by_id(item_id)

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
        """Uloží body a zachová existující ID (kvůli vazbám úkolů)."""
        from moduly.schuzky.sluzby.meeting_item_task_service import (
            meeting_item_task_service,
        )

        normalized = self._normalize_items(items)
        existing = {
            item.id: item for item in self.repository.get_for_meeting(meeting_id)
        }
        keep_ids: set[int] = set()
        saved: list[MeetingAgendaItem] = []

        for data in normalized:
            item_id = data.get("id")
            if item_id is not None and int(item_id) in existing:
                item = existing[int(item_id)]
                item.display_order = int(data["display_order"])
                item.title = data["title"]
                item.moje_sdeleni = data["moje_sdeleni"]
                item.prubeh_jednani = data["prubeh_jednani"]
                item.zaver = data["zaver"]
                saved_item = self.repository.update(item)
                saved.append(saved_item)
                keep_ids.add(saved_item.id)
            else:
                item = MeetingAgendaItem(
                    meeting_id=int(meeting_id),
                    display_order=int(data["display_order"]),
                    title=data["title"],
                    moje_sdeleni=data["moje_sdeleni"],
                    prubeh_jednani=data["prubeh_jednani"],
                    zaver=data["zaver"],
                )
                saved_item = self.repository.add(item)
                saved.append(saved_item)
                keep_ids.add(saved_item.id)

        for existing_id in existing:
            if existing_id in keep_ids:
                continue
            meeting_item_task_service.unlink_all_for_item(meeting_id, existing_id)
            self.repository.delete_by_id(existing_id)

        return saved

    def _normalize_items(self, items: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, raw in enumerate(items or []):
            data = {
                "title": str(raw.get("title") or "").strip(),
                "moje_sdeleni": str(raw.get("moje_sdeleni") or ""),
                "prubeh_jednani": str(raw.get("prubeh_jednani") or ""),
                "zaver": str(raw.get("zaver") or ""),
                "display_order": (index + 1) * 10,
            }
            raw_id = raw.get("id")
            if raw_id is not None and str(raw_id).strip() != "":
                try:
                    data["id"] = int(raw_id)
                except (TypeError, ValueError):
                    pass
            normalized.append(data)
        return normalized


meeting_agenda_item_service = MeetingAgendaItemService()
