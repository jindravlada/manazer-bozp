"""Služba evidence událostí (interně schůzky)."""

from __future__ import annotations

import json
from datetime import datetime

from moduly.nastaveni.sluzby.person_service import person_service
from moduly.schuzky.constants import (
    DEFAULT_MEETING_PRIORITY,
    DEFAULT_MEETING_STATUS,
    END_BEFORE_START_MESSAGE,
    MEETING_PRIORITIES,
    MEETING_STATUSES,
)
from moduly.schuzky.modely.meeting import Meeting
from moduly.schuzky.repository.meeting_repository import MeetingRepository
from moduly.schuzky.sluzby.meeting_event_type_service import meeting_event_type_service


class MeetingValidationError(ValueError):
    """Neplatná data události."""


class MeetingService:
    def __init__(self):
        self.repository = MeetingRepository()

    def get_all(self) -> list[Meeting]:
        return self.repository.get_all()

    def get_by_id(self, meeting_id: int) -> Meeting | None:
        return self.repository.get_by_id(meeting_id)

    def create_meeting(
        self,
        *,
        title: str = "",
        event_type: str = "",
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        location: str = "",
        organizer_person_id: int | None = None,
        participant_ids: list[int] | None = None,
        agenda: str = "",
        status: str = DEFAULT_MEETING_STATUS,
        priority: str = DEFAULT_MEETING_PRIORITY,
        proceedings: str = "",
        conclusions: str = "",
        notes: str = "",
    ) -> Meeting:
        self.validate_times(starts_at, ends_at)
        status = status if status in MEETING_STATUSES else DEFAULT_MEETING_STATUS
        priority = self.normalize_priority(priority)
        meeting = Meeting(
            title=(title or "").strip(),
            event_type=meeting_event_type_service.normalize(event_type),
            starts_at=starts_at,
            ends_at=ends_at,
            location=(location or "").strip(),
            organizer_person_id=organizer_person_id,
            organizer_name=self._person_name(organizer_person_id),
            participant_ids_json=self._encode_ids(participant_ids),
            participant_names=self._participant_names(participant_ids),
            agenda=agenda or "",
            proceedings=proceedings or "",
            conclusions=conclusions or "",
            notes=notes or "",
            status=status,
            priority=priority,
        )
        return self.repository.add(meeting)

    def update_meeting(
        self,
        meeting_id: int,
        *,
        title: str = "",
        event_type: str = "",
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        location: str = "",
        organizer_person_id: int | None = None,
        participant_ids: list[int] | None = None,
        agenda: str = "",
        status: str = DEFAULT_MEETING_STATUS,
        priority: str = DEFAULT_MEETING_PRIORITY,
        proceedings: str = "",
        conclusions: str = "",
        notes: str = "",
    ) -> Meeting:
        meeting = self.repository.get_by_id(meeting_id)
        if meeting is None:
            raise MeetingValidationError("Událost nebyla nalezena.")

        self.validate_times(starts_at, ends_at)
        status = status if status in MEETING_STATUSES else DEFAULT_MEETING_STATUS
        priority = self.normalize_priority(priority)

        meeting.title = (title or "").strip()
        meeting.event_type = meeting_event_type_service.normalize(event_type)
        meeting.starts_at = starts_at
        meeting.ends_at = ends_at
        meeting.location = (location or "").strip()
        meeting.organizer_person_id = organizer_person_id
        meeting.organizer_name = self._person_name(organizer_person_id)
        meeting.participant_ids_json = self._encode_ids(participant_ids)
        meeting.participant_names = self._participant_names(participant_ids)
        meeting.agenda = agenda or ""
        meeting.proceedings = proceedings or ""
        meeting.conclusions = conclusions or ""
        meeting.notes = notes or ""
        meeting.status = status
        meeting.priority = priority
        meeting.updated_at = datetime.now()
        return self.repository.update(meeting)

    @staticmethod
    def normalize_priority(value: str | None) -> str:
        text = (value or "").strip()
        if text in MEETING_PRIORITIES:
            return text
        return DEFAULT_MEETING_PRIORITY

    def validate_times(
        self,
        starts_at: datetime | None,
        ends_at: datetime | None,
    ) -> None:
        if starts_at is not None and ends_at is not None and ends_at < starts_at:
            raise MeetingValidationError(END_BEFORE_START_MESSAGE)

    def parse_participant_ids(self, meeting: Meeting) -> list[int]:
        raw = (meeting.participant_ids_json or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        result: list[int] = []
        for item in data:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
        return result

    def _encode_ids(self, person_ids: list[int] | None) -> str:
        ids = [int(value) for value in (person_ids or [])]
        return json.dumps(ids, ensure_ascii=False)

    def _person_name(self, person_id: int | None) -> str:
        if person_id is None:
            return ""
        person = person_service.get_by_id(person_id)
        return person.display_name if person is not None else ""

    def _participant_names(self, person_ids: list[int] | None) -> str:
        names: list[str] = []
        for person_id in person_ids or []:
            name = self._person_name(person_id)
            if name:
                names.append(name)
        return ", ".join(names)


meeting_service = MeetingService()
