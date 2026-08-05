"""Služba šablon událostí."""

from __future__ import annotations

import json
from datetime import datetime

from moduly.schuzky.constants import (
    DEFAULT_AGENDA_ITEM_STATUS,
    DEFAULT_EVENT_TYPE,
    DEFAULT_MEETING_PRIORITY,
    DEFAULT_MEETING_STATUS,
)
from moduly.schuzky.modely.meeting_template import MeetingTemplate
from moduly.schuzky.repository.meeting_template_repository import MeetingTemplateRepository
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.sluzby.meeting_event_type_service import meeting_event_type_service
from moduly.schuzky.sluzby.meeting_service import meeting_service


class MeetingTemplateValidationError(ValueError):
    """Neplatná data šablony události."""


class MeetingTemplateService:
    def __init__(self) -> None:
        self.repository = MeetingTemplateRepository()

    def get_all(self) -> list[MeetingTemplate]:
        return self.repository.get_all()

    def get_by_id(self, template_id: int) -> MeetingTemplate | None:
        return self.repository.get_by_id(template_id)

    def create_template(
        self,
        *,
        name: str,
        event_type: str = "",
        title: str = "",
        location: str = "",
        priority: str = DEFAULT_MEETING_PRIORITY,
        organizer_person_id: int | None = None,
        participant_ids: list[int] | None = None,
        external_participants: list[dict] | None = None,
        agenda_items: list[dict] | None = None,
    ) -> MeetingTemplate:
        template_name = (name or "").strip()
        if not template_name:
            raise MeetingTemplateValidationError("Zadejte název šablony.")

        template = MeetingTemplate(
            name=template_name,
            event_type=meeting_event_type_service.normalize(event_type),
            title=(title or "").strip(),
            location=(location or "").strip(),
            priority=meeting_service.normalize_priority(priority),
            organizer_person_id=organizer_person_id,
            participant_ids_json=meeting_service._encode_ids(participant_ids),
            external_participants_json=meeting_service._encode_externals(
                external_participants or []
            ),
            agenda_items_json=self._encode_agenda_items(agenda_items),
        )
        return self.repository.add(template)

    def update_template(
        self,
        template_id: int,
        *,
        name: str,
        event_type: str = "",
        title: str = "",
        location: str = "",
        priority: str = DEFAULT_MEETING_PRIORITY,
        organizer_person_id: int | None = None,
        participant_ids: list[int] | None = None,
        external_participants: list[dict] | None = None,
        agenda_items: list[dict] | None = None,
    ) -> MeetingTemplate:
        template = self.repository.get_by_id(template_id)
        if template is None:
            raise MeetingTemplateValidationError("Šablona nebyla nalezena.")

        template_name = (name or "").strip()
        if not template_name:
            raise MeetingTemplateValidationError("Zadejte název šablony.")

        template.name = template_name
        template.event_type = meeting_event_type_service.normalize(event_type)
        template.title = (title or "").strip()
        template.location = (location or "").strip()
        template.priority = meeting_service.normalize_priority(priority)
        template.organizer_person_id = organizer_person_id
        template.participant_ids_json = meeting_service._encode_ids(participant_ids)
        template.external_participants_json = meeting_service._encode_externals(
            external_participants or []
        )
        template.agenda_items_json = self._encode_agenda_items(agenda_items)
        template.updated_at = datetime.now()
        return self.repository.update(template)

    def delete_template(self, template_id: int) -> bool:
        return self.repository.delete(template_id)

    def agenda_item_count(self, template: MeetingTemplate) -> int:
        return len(self.parse_agenda_items(template))

    def parse_participant_ids(self, template: MeetingTemplate) -> list[int]:
        return meeting_service.parse_participant_ids(
            type("Obj", (), {"participant_ids_json": template.participant_ids_json})()
        )

    def parse_external_participants(self, template: MeetingTemplate) -> list[dict]:
        return meeting_service.parse_external_participants(
            type(
                "Obj",
                (),
                {"external_participants_json": template.external_participants_json},
            )()
        )

    def parse_agenda_items(self, template: MeetingTemplate) -> list[dict]:
        raw = (template.agenda_items_json or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return self.normalize_agenda_items(data)

    def normalize_agenda_items(self, items: list[dict] | None) -> list[dict]:
        """Jen název tématu, Moje sdělení a výchozí stav – bez průběhu/závěru/úkolů."""
        result: list[dict] = []
        for index, raw in enumerate(items or []):
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or "").strip()
            moje = str(raw.get("moje_sdeleni") or "")
            status = meeting_agenda_item_service.normalize_status(raw.get("status"))
            if not title and not moje.strip() and status == DEFAULT_AGENDA_ITEM_STATUS:
                continue
            result.append(
                {
                    "title": title,
                    "moje_sdeleni": moje,
                    "status": status,
                    "prubeh_jednani": "",
                    "zaver": "",
                    "display_order": (index + 1) * 10,
                }
            )
        return result

    def meeting_data_from_template(self, template: MeetingTemplate) -> dict:
        """Data pro novou Událost: bez data/času, stav Naplánováno."""
        return {
            "title": template.title or "",
            "event_type": meeting_event_type_service.normalize(
                template.event_type or DEFAULT_EVENT_TYPE
            ),
            "starts_at": None,
            "ends_at": None,
            "location": template.location or "",
            "organizer_person_id": template.organizer_person_id,
            "participant_ids": self.parse_participant_ids(template),
            "external_participants": self.parse_external_participants(template),
            "agenda": "",
            "status": DEFAULT_MEETING_STATUS,
            "priority": meeting_service.normalize_priority(template.priority),
            "proceedings": "",
            "conclusions": "",
            "notes": "",
        }

    def _encode_agenda_items(self, items: list[dict] | None) -> str:
        normalized = self.normalize_agenda_items(items)
        payload = [
            {
                "title": item["title"],
                "moje_sdeleni": item["moje_sdeleni"],
                "status": item["status"],
            }
            for item in normalized
        ]
        return json.dumps(payload, ensure_ascii=False)


meeting_template_service = MeetingTemplateService()
