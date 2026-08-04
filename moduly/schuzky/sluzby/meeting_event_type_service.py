"""Služba společného číselníku typů událostí."""

from __future__ import annotations

from moduly.schuzky.constants import DEFAULT_EVENT_TYPE, DEFAULT_EVENT_TYPES
from moduly.schuzky.repository.meeting_event_type_repository import (
    MeetingEventTypeRepository,
)


class MeetingEventTypeService:
    def __init__(self):
        self.repository = MeetingEventTypeRepository()

    def get_active_names(self) -> list[str]:
        names = [item.name for item in self.repository.get_all(include_inactive=False)]
        if names:
            return names
        return list(DEFAULT_EVENT_TYPES)

    def normalize(self, value: str | None) -> str:
        name = (value or "").strip()
        if not name:
            return DEFAULT_EVENT_TYPE
        active = self.get_active_names()
        for item in active:
            if item.casefold() == name.casefold():
                return item
        return name


meeting_event_type_service = MeetingEventTypeService()
