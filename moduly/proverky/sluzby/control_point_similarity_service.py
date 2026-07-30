"""Sběr kandidátů kontrolních otázek (bodů) pro SIMILARITY-1."""

from __future__ import annotations

from dataclasses import dataclass

from core.services.text_similarity_service import (
    SimilarityCandidate,
    SimilarityMatch,
    find_similar_texts,
)
from moduly.proverky.constants import MODULE_NAME
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service


@dataclass(frozen=True)
class ControlPointSimilarityCandidate:
    """Kontrolní otázka včetně umístění v metodice."""

    composite_id: str
    area_id: str
    area_name: str
    section_id: str
    section_name: str
    item_id: str
    text: str

    @property
    def location_label(self) -> str:
        return f"{MODULE_NAME} → {self.area_name} → {self.section_name}"


@dataclass(frozen=True)
class ControlPointSimilarityMatch:
    match: SimilarityMatch
    candidate: ControlPointSimilarityCandidate

    @property
    def location_label(self) -> str:
        return self.candidate.location_label


def make_control_point_composite_id(area_id: str, section_id: str, item_id: str) -> str:
    return f"{area_id}::{section_id}::{item_id}"


def parse_control_point_composite_id(composite_id: str) -> tuple[str, str, str] | None:
    parts = str(composite_id or "").split("::")
    if len(parts) != 3:
        return None
    area_id, section_id, item_id = (part.strip() for part in parts)
    if not area_id or not section_id or not item_id:
        return None
    return area_id, section_id, item_id


def collect_control_point_candidates(
    *,
    include_inactive: bool = True,
    override_section_items: dict[tuple[str, str], list[dict]] | None = None,
) -> list[ControlPointSimilarityCandidate]:
    """Všechny kontrolní body napříč oblastmi a sekcemi metodiky prověrek."""
    overrides = override_section_items or {}
    results: list[ControlPointSimilarityCandidate] = []

    for area in proverky_knowledge_service.get_areas(include_inactive=True):
        if not area.has_knowledge_file:
            continue
        sections = proverky_knowledge_service.list_sections(
            area.id,
            include_inactive=include_inactive,
        )
        for section in sections:
            section_id = str(section.get("id") or "").strip()
            if not section_id:
                continue
            section_name = str(section.get("nazev") or section_id).strip() or section_id
            items = overrides.get((area.id, section_id))
            if items is None:
                items = list(section.get("kontrolni_body") or [])

            for raw in items:
                if not isinstance(raw, dict):
                    continue
                if not include_inactive and not raw.get("aktivni", True):
                    continue
                item_id = str(raw.get("id") or "").strip()
                nazev = str(raw.get("nazev") or "").strip()
                if not item_id or not nazev:
                    continue
                results.append(
                    ControlPointSimilarityCandidate(
                        composite_id=make_control_point_composite_id(
                            area.id, section_id, item_id
                        ),
                        area_id=area.id,
                        area_name=area.nazev,
                        section_id=section_id,
                        section_name=section_name,
                        item_id=item_id,
                        text=nazev,
                    )
                )
    return results


def find_similar_control_points(
    query_text: str,
    *,
    exclude_composite_ids: list[str] | None = None,
    include_inactive: bool = True,
    override_section_items: dict[tuple[str, str], list[dict]] | None = None,
) -> list[ControlPointSimilarityMatch]:
    """Najde podobné kontrolní otázky vůči ``query_text``."""
    catalog = collect_control_point_candidates(
        include_inactive=include_inactive,
        override_section_items=override_section_items,
    )
    by_id = {item.composite_id: item for item in catalog}
    generic = find_similar_texts(
        query_text,
        [
            SimilarityCandidate(id=item.composite_id, text=item.text)
            for item in catalog
        ],
        exclude_ids=exclude_composite_ids,
    )
    return [
        ControlPointSimilarityMatch(match=item, candidate=by_id[item.id])
        for item in generic
        if item.id in by_id
    ]
