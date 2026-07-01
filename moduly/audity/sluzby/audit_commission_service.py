from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.audity.constants import (
    COMMISSION_DUPLICATE_PERSON_MESSAGE,
    COMMISSION_MEMBER_NAME_REQUIRED_MESSAGE,
    COMMISSION_PERSON_ROLE_REQUIRED_MESSAGE,
    COMMISSION_RECORD_INVITED,
    COMMISSION_RECORD_LEADER,
    COMMISSION_RECORD_MEMBER,
    COMMISSION_RECORD_TYPES,
    COMMISSION_RECORD_UNION,
    COMMISSION_RECORD_WORKPLACE,
    COMMISSION_REQUIRES_LEADER_MESSAGE,
    COMMISSION_REQUIRES_UNION_MESSAGE,
    COMMISSION_REQUIRES_WORKPLACE_MESSAGE,
    COMMISSION_THP_ROLE_REQUIRED_MESSAGE,
    COMMISSION_UNKNOWN_RECORD_TYPE_MESSAGE,
)
from moduly.audity.modely.audit_commission_member import AuditCommissionMember
from moduly.audity.repository.audit_commission_repository import AuditCommissionRepository


class AuditCommissionService:
    def __init__(self) -> None:
        self.repository = AuditCommissionRepository()

    def get_for_audit(self, audit_id: int) -> list[AuditCommissionMember]:
        return self.repository.get_for_audit(audit_id, active_only=True)

    def delete_for_audit(self, audit_id: int) -> int:
        return self.repository.delete_for_audit(audit_id)

    def save_members(self, audit_id: int, members: list[dict]) -> list[AuditCommissionMember]:
        validated = self.validate_members(members)
        self.repository.delete_for_audit(audit_id)

        saved: list[AuditCommissionMember] = []
        for member_data in validated:
            member = AuditCommissionMember(
                audit_id=audit_id,
                record_type=member_data["record_type"],
                thp_worker_id=member_data.get("thp_worker_id"),
                person_id=member_data.get("person_id"),
                display_name=member_data["display_name"],
                role_text=member_data.get("role_text"),
                note_text=member_data.get("note_text"),
                display_order=int(member_data.get("display_order") or 0),
                active=bool(member_data.get("active", True)),
            )
            saved.append(self.repository.add(member))
        return saved

    def validate_members(self, members: list[dict]) -> list[dict]:
        normalized = [self._normalize_member(member) for member in members if member.get("active", True)]

        leaders = [
            member for member in normalized if member["record_type"] == COMMISSION_RECORD_LEADER
        ]
        if len(leaders) != 1:
            raise ValueError(COMMISSION_REQUIRES_LEADER_MESSAGE)

        workplace_reps = [
            member for member in normalized if member["record_type"] == COMMISSION_RECORD_WORKPLACE
        ]
        if len(workplace_reps) != 1:
            raise ValueError(COMMISSION_REQUIRES_WORKPLACE_MESSAGE)

        union_reps = [
            member for member in normalized if member["record_type"] == COMMISSION_RECORD_UNION
        ]
        if len(union_reps) != 1:
            raise ValueError(COMMISSION_REQUIRES_UNION_MESSAGE)

        for member in normalized:
            record_type = member["record_type"]
            if record_type not in COMMISSION_RECORD_TYPES:
                raise ValueError(
                    COMMISSION_UNKNOWN_RECORD_TYPE_MESSAGE.format(record_type=record_type)
                )
            if not member["display_name"]:
                raise ValueError(COMMISSION_MEMBER_NAME_REQUIRED_MESSAGE)
            if record_type in {
                COMMISSION_RECORD_LEADER,
                COMMISSION_RECORD_WORKPLACE,
                COMMISSION_RECORD_MEMBER,
            }:
                if member.get("thp_worker_id") is None:
                    raise ValueError(COMMISSION_THP_ROLE_REQUIRED_MESSAGE)
            if record_type in {COMMISSION_RECORD_UNION, COMMISSION_RECORD_INVITED}:
                if member.get("person_id") is None:
                    raise ValueError(COMMISSION_PERSON_ROLE_REQUIRED_MESSAGE)

        self._validate_unique_persons(normalized)

        return normalized

    def _validate_unique_persons(self, members: list[dict]) -> None:
        thp_worker_ids = [
            member["thp_worker_id"]
            for member in members
            if member["record_type"]
            in {COMMISSION_RECORD_LEADER, COMMISSION_RECORD_WORKPLACE, COMMISSION_RECORD_MEMBER}
            and member.get("thp_worker_id") is not None
        ]
        if len(thp_worker_ids) != len(set(thp_worker_ids)):
            raise ValueError(COMMISSION_DUPLICATE_PERSON_MESSAGE)

        person_ids = [
            member["person_id"]
            for member in members
            if member["record_type"] in {COMMISSION_RECORD_UNION, COMMISSION_RECORD_INVITED}
            and member.get("person_id") is not None
        ]
        if len(person_ids) != len(set(person_ids)):
            raise ValueError(COMMISSION_DUPLICATE_PERSON_MESSAGE)

    def member_to_dict(self, member: AuditCommissionMember) -> dict:
        return {
            "id": member.id,
            "record_type": member.record_type,
            "thp_worker_id": member.thp_worker_id,
            "person_id": member.person_id,
            "display_name": member.display_name,
            "role_text": member.role_text,
            "note_text": member.note_text,
            "display_order": member.display_order,
            "active": member.active,
        }

    def _normalize_member(self, member: dict) -> dict:
        record_type = str(member.get("record_type") or "").strip()
        role_text = member.get("role_text")
        note_text = member.get("note_text")
        return {
            "record_type": record_type,
            "thp_worker_id": member.get("thp_worker_id"),
            "person_id": member.get("person_id"),
            "display_name": self._resolve_display_name(
                thp_worker_id=member.get("thp_worker_id"),
                person_id=member.get("person_id"),
                display_name=str(member.get("display_name") or "").strip(),
            ),
            "role_text": str(role_text).strip() if role_text else None,
            "note_text": str(note_text).strip() if note_text else None,
            "display_order": member.get("display_order"),
            "active": bool(member.get("active", True)),
        }

    @staticmethod
    def _resolve_display_name(
        *,
        thp_worker_id: int | None,
        person_id: int | None,
        display_name: str,
    ) -> str:
        if thp_worker_id is not None:
            worker = settings_service.get_worker_by_id(thp_worker_id)
            if worker is not None:
                return worker.display_name
        if person_id is not None:
            person = person_service.get_by_id(person_id)
            if person is not None:
                return person.display_name
        return display_name.strip()


audit_commission_service = AuditCommissionService()
