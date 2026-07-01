from datetime import date

from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.tymy.modely.team import Team
from moduly.tymy.modely.team_member import TeamMember
from moduly.tymy.repository.team_member_repository import TeamMemberRepository
from moduly.tymy.repository.team_repository import TeamRepository
from moduly.tymy.serializace import team_from_dict
from moduly.tymy.sluzby.team_catalog_service import team_catalog_service
from moduly.tymy.team_detail import TeamDetail

_UNSET = object()


class TeamService:
    def __init__(self) -> None:
        self.team_repository = TeamRepository()
        self.member_repository = TeamMemberRepository()

    def get_all_teams(self) -> list[Team]:
        return self.team_repository.get_all()

    def get_active_teams(self) -> list[Team]:
        return self.team_repository.get_active()

    def get_team(self, team_id: int) -> Team | None:
        return self.team_repository.get_by_id(team_id)

    def get_team_detail(self, team_id: int) -> TeamDetail | None:
        team = self.team_repository.get_by_id(team_id)
        if team is None:
            return None
        members = self.member_repository.get_for_team(team_id)
        return TeamDetail(team=team, members=members)

    def create_team(
        self,
        *,
        name: str,
        team_type_id: str,
        description: str = "",
        active: bool = True,
        valid_from: date | None = None,
        valid_to: date | None = None,
    ) -> Team:
        team_type = team_catalog_service.get_team_type_by_id(team_type_id)
        if team_type is None:
            raise ValueError(f"Neznámý typ týmu: {team_type_id}")

        team = Team(
            name=name.strip(),
            description=description.strip(),
            team_type_id=team_type.id,
            team_type_name=team_type.nazev,
            active=active,
            valid_from=valid_from or date.today(),
            valid_to=valid_to,
        )
        return self.team_repository.add(team)

    def update_team(
        self,
        team_id: int,
        *,
        name: str | None = None,
        team_type_id: str | None = None,
        description: str | None = None,
        active: bool | None = None,
        valid_from: date | None = None,
        valid_to: date | None | object = _UNSET,
    ) -> Team | None:
        team = self.team_repository.get_by_id(team_id)
        if team is None:
            return None

        if name is not None:
            team.name = name.strip()
        if description is not None:
            team.description = description.strip()
        if active is not None:
            team.active = active
        if valid_from is not None:
            team.valid_from = valid_from
        if valid_to is not _UNSET:
            team.valid_to = valid_to  # type: ignore[assignment]
        if team_type_id is not None:
            team_type = team_catalog_service.get_team_type_by_id(team_type_id)
            if team_type is None:
                raise ValueError(f"Neznámý typ týmu: {team_type_id}")
            team.team_type_id = team_type.id
            team.team_type_name = team_type.nazev

        return self.team_repository.update(team)

    def delete_team(self, team_id: int) -> bool:
        self.member_repository.delete_for_team(team_id)
        return self.team_repository.delete(team_id)

    def get_members(self, team_id: int) -> list[TeamMember]:
        return self.member_repository.get_for_team(team_id)

    def add_member(
        self,
        team_id: int,
        *,
        role_id: str,
        thp_worker_id: int | None = None,
        person_id: int | None = None,
        person_name: str = "",
        mandatory: bool = False,
        display_order: int | None = None,
    ) -> TeamMember:
        if self.team_repository.get_by_id(team_id) is None:
            raise ValueError(f"Tým {team_id} neexistuje")

        role = team_catalog_service.get_team_role_by_id(role_id)
        if role is None:
            raise ValueError(f"Neznámá role v týmu: {role_id}")

        resolved_name = self._resolve_person_name(
            thp_worker_id=thp_worker_id,
            person_id=person_id,
            person_name=person_name,
        )
        if not resolved_name:
            raise ValueError("Člen týmu musí mít určenou osobu.")

        member = TeamMember(
            team_id=team_id,
            thp_worker_id=thp_worker_id,
            person_id=person_id if thp_worker_id is None else None,
            person_name=resolved_name,
            role_id=role.id,
            role_name=role.nazev,
            mandatory=mandatory,
            display_order=(
                display_order
                if display_order is not None
                else self.member_repository.max_display_order(team_id) + 1
            ),
        )
        return self.member_repository.add(member)

    def update_member(
        self,
        member_id: int,
        *,
        role_id: str | None = None,
        thp_worker_id: int | None | object = _UNSET,
        person_id: int | None | object = _UNSET,
        person_name: str | None = None,
        mandatory: bool | None = None,
        display_order: int | None = None,
    ) -> TeamMember | None:
        member = self.member_repository.get_by_id(member_id)
        if member is None:
            return None

        if role_id is not None:
            role = team_catalog_service.get_team_role_by_id(role_id)
            if role is None:
                raise ValueError(f"Neznámá role v týmu: {role_id}")
            member.role_id = role.id
            member.role_name = role.nazev

        if thp_worker_id is not _UNSET:
            member.thp_worker_id = thp_worker_id  # type: ignore[assignment]
            if thp_worker_id is not None:
                member.person_id = None
        if person_id is not _UNSET:
            member.person_id = person_id  # type: ignore[assignment]
            if person_id is not None:
                member.thp_worker_id = None

        if person_name is not None or thp_worker_id is not _UNSET or person_id is not _UNSET:
            member.person_name = self._resolve_person_name(
                thp_worker_id=member.thp_worker_id,
                person_id=member.person_id,
                person_name=person_name if person_name is not None else member.person_name,
            )

        if mandatory is not None:
            member.mandatory = mandatory
        if display_order is not None:
            member.display_order = display_order

        return self.member_repository.update(member)

    def delete_member(self, member_id: int) -> bool:
        return self.member_repository.delete(member_id)

    def create_team_from_dict(self, data: dict) -> TeamDetail:
        payload = team_from_dict(data)
        team = self.create_team(
            name=payload["name"],
            team_type_id=payload["team_type_id"],
            description=payload["description"],
            active=payload["active"],
            valid_from=payload["valid_from"],
            valid_to=payload["valid_to"],
        )
        members: list[TeamMember] = []
        for index, member_data in enumerate(payload["members"], start=1):
            members.append(
                self.add_member(
                    team.id,
                    role_id=member_data["role_id"],
                    thp_worker_id=member_data.get("thp_worker_id"),
                    person_id=member_data.get("person_id"),
                    person_name=member_data.get("person_name", ""),
                    mandatory=member_data.get("mandatory", False),
                    display_order=member_data.get("display_order") or index * 10,
                )
            )
        return TeamDetail(team=team, members=members)

    def _resolve_person_name(
        self,
        *,
        thp_worker_id: int | None,
        person_id: int | None,
        person_name: str,
    ) -> str:
        if thp_worker_id is not None:
            worker = settings_service.get_worker_by_id(thp_worker_id)
            if worker is not None:
                return worker.display_name
        if person_id is not None:
            person = person_service.get_by_id(person_id)
            if person is not None:
                return person.display_name
        return person_name.strip()


team_service = TeamService()
