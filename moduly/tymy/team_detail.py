from dataclasses import dataclass

from moduly.tymy.modely.team import Team
from moduly.tymy.modely.team_member import TeamMember


@dataclass
class TeamDetail:
    team: Team
    members: list[TeamMember]
