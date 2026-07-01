from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from moduly.tymy.modely.team import Team
from moduly.tymy.modely.team_member import TeamMember
from moduly.tymy.team_detail import TeamDetail


def _date_to_str(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _date_from_str(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _datetime_to_str(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def team_member_to_dict(member: TeamMember) -> dict[str, Any]:
    return {
        "id": member.id,
        "team_id": member.team_id,
        "thp_worker_id": member.thp_worker_id,
        "person_id": member.person_id,
        "person_name": member.person_name,
        "role_id": member.role_id,
        "role_name": member.role_name,
        "mandatory": member.mandatory,
        "display_order": member.display_order,
    }


def team_to_dict(team: Team, members: list[TeamMember] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "team_type_id": team.team_type_id,
        "team_type_name": team.team_type_name,
        "active": team.active,
        "valid_from": _date_to_str(team.valid_from),
        "valid_to": _date_to_str(team.valid_to),
        "created_at": _datetime_to_str(team.created_at),
        "updated_at": _datetime_to_str(team.updated_at),
    }
    if members is not None:
        payload["members"] = [team_member_to_dict(member) for member in members]
    return payload


def team_detail_to_dict(detail: TeamDetail) -> dict[str, Any]:
    return team_to_dict(detail.team, detail.members)


def teams_to_json(details: list[TeamDetail]) -> str:
    return json.dumps(
        [team_detail_to_dict(detail) for detail in details],
        ensure_ascii=False,
        indent=2,
    )


def team_member_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "role_id": str(data.get("role_id") or "").strip(),
        "thp_worker_id": data.get("thp_worker_id"),
        "person_id": data.get("person_id"),
        "person_name": str(data.get("person_name") or "").strip(),
        "mandatory": bool(data.get("mandatory", False)),
        "display_order": data.get("display_order"),
    }


def team_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(data.get("name") or "").strip(),
        "description": str(data.get("description") or "").strip(),
        "team_type_id": str(data.get("team_type_id") or "").strip(),
        "active": bool(data.get("active", True)),
        "valid_from": _date_from_str(data.get("valid_from")),
        "valid_to": _date_from_str(data.get("valid_to")),
        "members": [
            team_member_from_dict(item)
            for item in (data.get("members") or [])
            if isinstance(item, dict)
        ],
    }
