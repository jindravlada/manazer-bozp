"""Služba evidence událostí (interně schůzky)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.schuzky.constants import (
    DEFAULT_EVENT_DURATION_HOURS,
    DEFAULT_MEETING_PRIORITY,
    DEFAULT_MEETING_STATUS,
    END_BEFORE_START_MESSAGE,
    LEGACY_STATUS_HELD,
    MEETING_PRIORITIES,
    MEETING_STATUSES,
    STATUS_CLOSED,
    STATUS_PLANNED,
)
from moduly.schuzky.modely.meeting import Meeting
from moduly.schuzky.repository.meeting_repository import MeetingRepository
from moduly.schuzky.sluzby.meeting_event_type_service import meeting_event_type_service
from moduly.schuzky.sluzby.meeting_participant_ref import (
    MEETING_SOURCE_PERSON,
    MEETING_SOURCE_THP_WORKER,
    normalize_participant_ref,
    normalize_participant_refs,
)


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
        remind_from: date | None = None,
        location: str = "",
        organizer_person_id: int | None = None,
        organizer_ref: dict | None = None,
        participant_ids: list[int] | None = None,
        participant_refs: list[dict] | None = None,
        external_participants: list[dict] | None = None,
        agenda: str = "",
        status: str = DEFAULT_MEETING_STATUS,
        priority: str = DEFAULT_MEETING_PRIORITY,
        proceedings: str = "",
        conclusions: str = "",
        notes: str = "",
    ) -> Meeting:
        self.validate_times(starts_at, ends_at)
        remind_from = self._normalized_remind_from(remind_from, starts_at)
        status = self.normalize_status(status)
        priority = self.normalize_priority(priority)
        externals = self.normalize_external_participants(external_participants or [])
        org = self._resolve_organizer_input(
            organizer_ref=organizer_ref,
            organizer_person_id=organizer_person_id,
        )
        refs = self._resolve_participant_input(
            participant_refs=participant_refs,
            participant_ids=participant_ids,
        )
        meeting = Meeting(
            title=(title or "").strip(),
            event_type=meeting_event_type_service.normalize(event_type),
            starts_at=starts_at,
            ends_at=ends_at,
            remind_from=remind_from,
            location=(location or "").strip(),
            organizer_person_id=org["legacy_person_id"],
            organizer_source_type=org["source_type"],
            organizer_source_id=org["source_id"],
            organizer_name=org["display_name"],
            participant_ids_json=self._encode_participant_refs(refs),
            external_participants_json=self._encode_externals(externals),
            participant_names=self._combined_participant_names_from_refs(refs, externals),
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
        remind_from: date | None = None,
        location: str = "",
        organizer_person_id: int | None = None,
        organizer_ref: dict | None = None,
        participant_ids: list[int] | None = None,
        participant_refs: list[dict] | None = None,
        external_participants: list[dict] | None = None,
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
        remind_from = self._normalized_remind_from(remind_from, starts_at)
        status = self.normalize_status(status)
        priority = self.normalize_priority(priority)

        if external_participants is not None:
            externals = self.normalize_external_participants(external_participants)
            meeting.external_participants_json = self._encode_externals(externals)
        else:
            externals = self.parse_external_participants(meeting)

        org = self._resolve_organizer_input(
            organizer_ref=organizer_ref,
            organizer_person_id=organizer_person_id,
        )
        refs = self._resolve_participant_input(
            participant_refs=participant_refs,
            participant_ids=participant_ids,
        )

        meeting.title = (title or "").strip()
        meeting.event_type = meeting_event_type_service.normalize(event_type)
        meeting.starts_at = starts_at
        meeting.ends_at = ends_at
        meeting.remind_from = remind_from
        meeting.location = (location or "").strip()
        meeting.organizer_person_id = org["legacy_person_id"]
        meeting.organizer_source_type = org["source_type"]
        meeting.organizer_source_id = org["source_id"]
        meeting.organizer_name = org["display_name"]
        meeting.participant_ids_json = self._encode_participant_refs(refs)
        meeting.participant_names = self._combined_participant_names_from_refs(
            refs, externals
        )
        meeting.agenda = agenda or ""
        meeting.proceedings = proceedings or ""
        meeting.conclusions = conclusions or ""
        meeting.notes = notes or ""
        meeting.status = status
        meeting.priority = priority
        meeting.updated_at = datetime.now()
        return self.repository.update(meeting)

    @staticmethod
    def normalize_status(value: str | None) -> str:
        text = (value or "").strip()
        if text == LEGACY_STATUS_HELD:
            return STATUS_CLOSED
        if text in MEETING_STATUSES:
            return text
        return DEFAULT_MEETING_STATUS

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
    def validate_remind_from(
        remind_from: date | None,
        starts_at: datetime | None,
    ) -> str | None:
        """Vrátí chybovou hlášku, pokud je remind_from neplatné."""
        if remind_from is None or starts_at is None:
            return None
        event_date = starts_at.date() if isinstance(starts_at, datetime) else starts_at
        if remind_from > event_date:
            return "Připomenout od nemůže být později než datum události."
        return None

    @classmethod
    def _normalized_remind_from(
        cls,
        remind_from: date | None,
        starts_at: datetime | None,
    ) -> date | None:
        error = cls.validate_remind_from(remind_from, starts_at)
        if error:
            raise MeetingValidationError(error)
        return remind_from

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

    def organizer_ref(self, meeting: Meeting) -> dict[str, Any] | None:
        source_type = (getattr(meeting, "organizer_source_type", None) or "").strip()
        source_id = getattr(meeting, "organizer_source_id", None)
        if source_type in (MEETING_SOURCE_PERSON, MEETING_SOURCE_THP_WORKER) and source_id:
            return normalize_participant_ref(
                {"source_type": source_type, "source_id": int(source_id)}
            )
        if meeting.organizer_person_id:
            return {
                "source_type": MEETING_SOURCE_PERSON,
                "source_id": int(meeting.organizer_person_id),
            }
        return None

    def parse_participant_refs(self, meeting: Meeting) -> list[dict[str, Any]]:
        raw = (meeting.participant_ids_json or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return normalize_participant_refs(data)

    def parse_participant_ids(self, meeting: Meeting) -> list[int]:
        """Legacy: jen Person ID z refs (pro starší volající)."""
        return [
            int(ref["source_id"])
            for ref in self.parse_participant_refs(meeting)
            if ref["source_type"] == MEETING_SOURCE_PERSON
        ]

    def parse_external_participants(self, meeting: Meeting) -> list[dict]:
        raw = (getattr(meeting, "external_participants_json", None) or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return self.normalize_external_participants(data)

    @staticmethod
    def normalize_external_participants(items: list | None) -> list[dict]:
        result: list[dict] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            full_name = str(item.get("full_name") or "").strip()
            if not full_name:
                continue
            result.append(
                {
                    "full_name": full_name,
                    "organization": str(item.get("organization") or "").strip(),
                    "function": str(item.get("function") or "").strip(),
                    "contact": str(item.get("contact") or "").strip(),
                    "note": str(item.get("note") or "").strip(),
                }
            )
        return result

    @staticmethod
    def external_participant_label(item: dict) -> str:
        name = str(item.get("full_name") or "").strip() or "Bez jména"
        organization = str(item.get("organization") or "").strip()
        if organization:
            return f"{name} ({organization})"
        return name

    def resolve_ref_display_name(self, ref: dict | None) -> str:
        normalized = normalize_participant_ref(ref) if ref else None
        if normalized is None:
            return ""
        if normalized["source_type"] == MEETING_SOURCE_THP_WORKER:
            worker = settings_service.get_worker_by_id(normalized["source_id"])
            if worker is None:
                return f"THP #{normalized['source_id']}"
            return worker.display_name or f"THP #{normalized['source_id']}"
        person = person_service.get_by_id(normalized["source_id"])
        if person is None:
            return f"Osoba #{normalized['source_id']}"
        return person.display_name or f"Osoba #{normalized['source_id']}"

    def _resolve_organizer_input(
        self,
        *,
        organizer_ref: dict | None,
        organizer_person_id: int | None,
    ) -> dict[str, Any]:
        ref = None
        if organizer_ref is not None:
            ref = normalize_participant_ref(organizer_ref)
        elif organizer_person_id is not None:
            ref = normalize_participant_ref(organizer_person_id)
        if ref is None:
            return {
                "source_type": None,
                "source_id": None,
                "legacy_person_id": None,
                "display_name": "",
            }
        display = self.resolve_ref_display_name(ref)
        legacy = (
            int(ref["source_id"])
            if ref["source_type"] == MEETING_SOURCE_PERSON
            else None
        )
        return {
            "source_type": ref["source_type"],
            "source_id": int(ref["source_id"]),
            "legacy_person_id": legacy,
            "display_name": display,
        }

    def _resolve_participant_input(
        self,
        *,
        participant_refs: list[dict] | None,
        participant_ids: list[int] | None,
    ) -> list[dict[str, Any]]:
        if participant_refs is not None:
            return normalize_participant_refs(participant_refs)
        if participant_ids is not None:
            return normalize_participant_refs(participant_ids)
        return []

    def _encode_participant_refs(self, refs: list[dict] | None) -> str:
        return json.dumps(normalize_participant_refs(refs), ensure_ascii=False)

    def _encode_ids(self, person_ids: list[int] | None) -> str:
        """Legacy helper – uloží Person ID jako polymorfní refs."""
        return self._encode_participant_refs(
            [
                {"source_type": MEETING_SOURCE_PERSON, "source_id": int(value)}
                for value in (person_ids or [])
            ]
        )

    def _encode_externals(self, items: list[dict] | None) -> str:
        return json.dumps(self.normalize_external_participants(items), ensure_ascii=False)

    def _person_name(self, person_id: int | None) -> str:
        if person_id is None:
            return ""
        person = person_service.get_by_id(person_id)
        return person.display_name if person is not None else ""

    def _combined_participant_names_from_refs(
        self,
        refs: list[dict] | None,
        external_participants: list[dict] | None,
    ) -> str:
        names: list[str] = []
        for ref in refs or []:
            label = self.resolve_ref_display_name(ref)
            if label:
                names.append(label)
        for item in external_participants or []:
            label = self.external_participant_label(item)
            if label:
                names.append(label)
        return ", ".join(names)


meeting_service = MeetingService()
