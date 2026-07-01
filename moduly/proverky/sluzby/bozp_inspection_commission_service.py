from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.proverky.constants import (
    COMMISSION_DUPLICATE_PERSON_MESSAGE,
    COMMISSION_RECORD_INVITED,
    COMMISSION_RECORD_LEADER,
    COMMISSION_RECORD_MEMBER,
    COMMISSION_RECORD_TYPES,
    COMMISSION_RECORD_UNION,
    COMMISSION_RECORD_WORKPLACE,
)
from moduly.proverky.modely.bozp_inspection_commission_member import BozpInspectionCommissionMember
from moduly.proverky.repository.bozp_inspection_commission_repository import (
    BozpInspectionCommissionRepository,
)


class BozpInspectionCommissionService:
    def __init__(self) -> None:
        self.repository = BozpInspectionCommissionRepository()

    def get_for_inspection(self, inspection_id: int) -> list[BozpInspectionCommissionMember]:
        return self.repository.get_for_inspection(inspection_id, active_only=True)

    def delete_for_inspection(self, inspection_id: int) -> int:
        return self.repository.delete_for_inspection(inspection_id)

    def save_members(self, inspection_id: int, members: list[dict]) -> list[BozpInspectionCommissionMember]:
        validated = self.validate_members(members)
        self.repository.delete_for_inspection(inspection_id)

        saved: list[BozpInspectionCommissionMember] = []
        for member_data in validated:
            member = BozpInspectionCommissionMember(
                inspection_id=inspection_id,
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
            raise ValueError("Prověrka musí mít právě jednoho vedoucího komise.")

        workplace_reps = [
            member for member in normalized if member["record_type"] == COMMISSION_RECORD_WORKPLACE
        ]
        if len(workplace_reps) != 1:
            raise ValueError("Prověrka musí mít právě jednoho zástupce pracoviště.")

        union_reps = [
            member for member in normalized if member["record_type"] == COMMISSION_RECORD_UNION
        ]
        if len(union_reps) != 1:
            raise ValueError("Prověrka musí mít právě jednoho zástupce odborové organizace.")

        for member in normalized:
            record_type = member["record_type"]
            if record_type not in COMMISSION_RECORD_TYPES:
                raise ValueError(f"Neznámý typ záznamu komise: {record_type}")
            if not member["display_name"]:
                raise ValueError("Každý člen komise musí mít vyplněné jméno.")
            if record_type in {
                COMMISSION_RECORD_LEADER,
                COMMISSION_RECORD_WORKPLACE,
                COMMISSION_RECORD_MEMBER,
            }:
                if member.get("thp_worker_id") is None:
                    raise ValueError(
                        "Vedoucí komise, zástupce pracoviště a členové komise musí být THP pracovníci."
                    )
            if record_type in {COMMISSION_RECORD_UNION, COMMISSION_RECORD_INVITED}:
                if member.get("person_id") is None:
                    raise ValueError("Zástupce odborů a přizvané osoby musí být ze seznamu Osob.")

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

    def member_to_dict(self, member: BozpInspectionCommissionMember) -> dict:
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


bozp_inspection_commission_service = BozpInspectionCommissionService()
