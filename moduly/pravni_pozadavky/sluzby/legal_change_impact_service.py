from dataclasses import dataclass

from core.shared.constants import ENTITY_LEGAL_CHANGE
from core.shared.sluzby.entity_link_service import entity_link_service
from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service


@dataclass(frozen=True)
class LegalChangeImpactLink:
    target_type: str
    target_id: int
    link_type: str
    note: str
    active: bool


@dataclass(frozen=True)
class LegalChangeImpactSummary:
    total_count: int
    counts_by_type: dict[str, int]
    links: list[LegalChangeImpactLink]


class LegalChangeImpactService:
    def build_summary(self, legal_change_id: int) -> LegalChangeImpactSummary | None:
        change = legal_change_service.get_by_id(legal_change_id)
        if change is None:
            return None

        entity_links = entity_link_service.list_for_source(
            ENTITY_LEGAL_CHANGE,
            legal_change_id,
            include_inactive=False,
        )
        impact_links = [
            LegalChangeImpactLink(
                target_type=link.target_type,
                target_id=link.target_id,
                link_type=link.link_type,
                note=link.note,
                active=link.active,
            )
            for link in entity_links
        ]
        counts_by_type: dict[str, int] = {}
        for link in impact_links:
            counts_by_type[link.target_type] = counts_by_type.get(link.target_type, 0) + 1

        return LegalChangeImpactSummary(
            total_count=len(impact_links),
            counts_by_type=counts_by_type,
            links=impact_links,
        )


legal_change_impact_service = LegalChangeImpactService()
