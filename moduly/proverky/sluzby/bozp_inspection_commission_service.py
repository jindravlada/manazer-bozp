from moduly.proverky.modely.bozp_inspection_commission_member import BozpInspectionCommissionMember
from moduly.proverky.repository.bozp_inspection_commission_repository import (
    BozpInspectionCommissionRepository,
)
from moduly.tymy.sluzby.team_service import team_service


class BozpInspectionCommissionService:
    def __init__(self) -> None:
        self.repository = BozpInspectionCommissionRepository()

    def get_for_inspection(self, inspection_id: int) -> list[BozpInspectionCommissionMember]:
        return self.repository.get_for_inspection(inspection_id)

    def delete_for_inspection(self, inspection_id: int) -> int:
        return self.repository.delete_for_inspection(inspection_id)

    def members_from_team(self, team_id: int) -> list[dict]:
        detail = team_service.get_team_detail(team_id)
        if detail is None:
            return []

        members: list[dict] = []
        for team_member in detail.members:
            members.append(self._member_from_team_template(team_member))
        return members

    def save_members(self, inspection_id: int, members: list[dict]) -> list[BozpInspectionCommissionMember]:
        self.repository.delete_for_inspection(inspection_id)

        saved: list[BozpInspectionCommissionMember] = []
        for index, member_data in enumerate(members, start=1):
            display_order = member_data.get("display_order")
            if display_order is None:
                display_order = index * 10

            member = BozpInspectionCommissionMember(
                inspection_id=inspection_id,
                team_member_id=member_data.get("team_member_id"),
                thp_worker_id=member_data.get("thp_worker_id"),
                person_id=member_data.get("person_id"),
                person_name=str(member_data.get("person_name") or "").strip(),
                role_id=str(member_data.get("role_id") or "").strip(),
                role_name=str(member_data.get("role_name") or "").strip(),
                mandatory=bool(member_data.get("mandatory", False)),
                participated=bool(member_data.get("participated", True)),
                ad_hoc=bool(member_data.get("ad_hoc", False)),
                display_order=int(display_order),
            )
            saved.append(self.repository.add(member))
        return saved

    def merge_team_template(
        self,
        current_members: list[dict],
        team_id: int,
        *,
        keep_ad_hoc: bool = True,
    ) -> list[dict]:
        ad_hoc_members = [
            dict(member) for member in current_members if member.get("ad_hoc")
        ] if keep_ad_hoc else []

        template_members = self.members_from_team(team_id)
        if not ad_hoc_members:
            return template_members

        next_order = max(
            (int(member.get("display_order") or 0) for member in template_members),
            default=0,
        )
        for index, member in enumerate(ad_hoc_members, start=1):
            member["display_order"] = next_order + index * 10

        return [*template_members, *ad_hoc_members]

    @staticmethod
    def member_to_dict(member: BozpInspectionCommissionMember) -> dict:
        return {
            "id": member.id,
            "team_member_id": member.team_member_id,
            "thp_worker_id": member.thp_worker_id,
            "person_id": member.person_id,
            "person_name": member.person_name,
            "role_id": member.role_id,
            "role_name": member.role_name,
            "mandatory": member.mandatory,
            "participated": member.participated,
            "ad_hoc": member.ad_hoc,
            "display_order": member.display_order,
        }

    @staticmethod
    def _member_from_team_template(team_member) -> dict:
        return {
            "id": None,
            "team_member_id": team_member.id,
            "thp_worker_id": team_member.thp_worker_id,
            "person_id": team_member.person_id,
            "person_name": team_member.person_name,
            "role_id": team_member.role_id,
            "role_name": team_member.role_name,
            "mandatory": team_member.mandatory,
            "participated": True,
            "ad_hoc": False,
            "display_order": team_member.display_order,
        }


bozp_inspection_commission_service = BozpInspectionCommissionService()
