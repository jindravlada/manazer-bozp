"""Služba evidence událostí (interně schůzky)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from moduly.nastaveni.sluzby.person_service import person_service
from moduly.schuzky.constants import (
    DEFAULT_EVENT_DURATION_HOURS,
    DEFAULT_MEETING_PRIORITY,
    DEFAULT_MEETING_STATUS,
    END_BEFORE_START_MESSAGE,
    MEETING_PRIORITIES,
    MEETING_STATUSES,
    STATUS_PLANNED,
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

    @staticmethod
    def effective_ends_at(
        starts_at: datetime | None,
        ends_at: datetime | None,
    ) -> datetime | None:
        """Ukončení pro kontrolu konfliktů; chybějící konec → +1 hodina (data nemění)."""
        if starts_at is None:
            return None
        if ends_at is not None:
            return ends_at
        return starts_at + timedelta(hours=DEFAULT_EVENT_DURATION_HOURS)

    @staticmethod
    def intervals_overlap(
        start_a: datetime,
        end_a: datetime,
        start_b: datetime,
        end_b: datetime,
    ) -> bool:
        """Překryv intervalů; navazující (konec == začátek) není konflikt."""
        return start_a < end_b and end_a > start_b

    @staticmethod
    def _normalize_dt(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(second=0, microsecond=0)

    def is_planned_start_in_past_forbidden(
        self,
        *,
        status: str,
        starts_at: datetime | None,
        existing: Meeting | None = None,
        now: datetime | None = None,
    ) -> bool:
        """
        True = uložení jako Naplánováno s minulým zahájením zakázat.

        Existující Naplánováno se stejným minulým zahájením (už v DB) neblokovat.
        """
        if (status or "").strip() != STATUS_PLANNED:
            return False
        start = self._normalize_dt(starts_at)
        if start is None:
            return False
        current = self._normalize_dt(now or datetime.now())
        assert current is not None
        if start >= current:
            return False

        if existing is None:
            return True

        was_planned = (existing.status or "").strip() == STATUS_PLANNED
        existing_start = self._normalize_dt(existing.starts_at)
        if was_planned and existing_start == start:
            return False
        return True

    def find_planned_conflicts(
        self,
        *,
        starts_at: datetime | None,
        ends_at: datetime | None,
        exclude_id: int | None = None,
    ) -> list[Meeting]:
        """Naplanované události s časovým překryvem (bez exclude_id)."""
        if starts_at is None:
            return []
        new_start = starts_at
        new_end = self.effective_ends_at(starts_at, ends_at)
        if new_end is None:
            return []

        conflicts: list[Meeting] = []
        for meeting in self.get_all():
            if exclude_id is not None and int(meeting.id) == int(exclude_id):
                continue
            if (meeting.status or "").strip() != STATUS_PLANNED:
                continue
            other_start = meeting.starts_at
            if other_start is None:
                continue
            other_end = self.effective_ends_at(other_start, meeting.ends_at)
            if other_end is None:
                continue
            if self.intervals_overlap(new_start, new_end, other_start, other_end):
                conflicts.append(meeting)
        conflicts.sort(key=lambda item: item.starts_at or datetime.max)
        return conflicts

    @staticmethod
    def format_conflict_line(meeting: Meeting) -> str:
        starts = meeting.starts_at
        if starts is None:
            return (meeting.title or "").strip() or "Bez názvu"
        ends = MeetingService.effective_ends_at(starts, meeting.ends_at)
        assert ends is not None
        if starts.date() == ends.date():
            when = (
                f"{starts.strftime('%d.%m.%Y')} "
                f"{starts.strftime('%H:%M')}–{ends.strftime('%H:%M')}"
            )
        else:
            when = (
                f"{starts.strftime('%d.%m.%Y %H:%M')}–"
                f"{ends.strftime('%d.%m.%Y %H:%M')}"
            )
        event_type = (getattr(meeting, "event_type", None) or "").strip() or "—"
        title = (meeting.title or "").strip() or "Bez názvu"
        parts = [when, event_type, title]
        location = (meeting.location or "").strip()
        if location:
            parts.append(location)
        return " · ".join(parts)

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
