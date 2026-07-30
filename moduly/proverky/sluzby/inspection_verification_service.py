"""Typ ověření kontrolních bodů (Dokumentace / Terén) pro metodiku i prověrku."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from moduly.proverky.constants import (
    VERIFICATION_TYPE_DEFAULT,
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
    ProverkyFindingKnowledgeContext,
)
from moduly.proverky.repository.bozp_inspection_verification_override_repository import (
    BozpInspectionVerificationOverrideRepository,
)
from moduly.proverky.sluzby.proverky_knowledge_service import (
    KnowledgeTreeNode,
    proverky_knowledge_service,
)

logger = logging.getLogger(__name__)

_VALID_VERIFICATION_TYPES = frozenset(
    {
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
    }
)

# Historické / alternativní zápisy → kanonické hodnoty projektu (dokumentace / teren).
_DOCUMENTATION_ALIASES = frozenset(
    {
        VERIFICATION_TYPE_DOCUMENTATION,
        "dokumentace",
        "documentation",
        "document",
        "docs",
        "doc",
    }
)
_TERRAIN_ALIASES = frozenset(
    {
        VERIFICATION_TYPE_TERRAIN,
        "teren",
        "terén",
        "terrain",
        "field",
        "teren",
    }
)


@dataclass(frozen=True)
class InspectionControlPointRef:
    """Kontrolní bod v kontextu prověrky včetně efektivního typu ověření."""

    area_id: str
    area_label: str
    section_id: str
    section_label: str
    control_point_id: str
    control_point_label: str
    control_point: dict
    methodology_verification_type: str
    effective_verification_type: str

    @property
    def knowledge_context(self) -> ProverkyFindingKnowledgeContext:
        return ProverkyFindingKnowledgeContext(
            area_id=self.area_id,
            area_label=self.area_label,
            section_id=self.section_id,
            section_label=self.section_label,
            control_point_id=self.control_point_id,
            control_point_label=self.control_point_label,
        )


class InspectionVerificationService:
    def __init__(self) -> None:
        self.repository = BozpInspectionVerificationOverrideRepository()

    @staticmethod
    def normalize_verification_type(value) -> str:
        """Sjednotí typ ověření na kanonické hodnoty projektu (dokumentace / teren)."""
        raw = str(value or "").strip()
        normalized = raw.casefold()
        if normalized in _DOCUMENTATION_ALIASES:
            return VERIFICATION_TYPE_DOCUMENTATION
        if normalized in _TERRAIN_ALIASES:
            return VERIFICATION_TYPE_TERRAIN
        if raw:
            logger.warning(
                "Neznámý typ ověření kontrolního bodu %r – použito výchozí %s.",
                value,
                VERIFICATION_TYPE_DEFAULT,
            )
        return VERIFICATION_TYPE_DEFAULT

    def methodology_verification_type(self, item: dict | None) -> str:
        if not isinstance(item, dict):
            return VERIFICATION_TYPE_DEFAULT
        return self.normalize_verification_type(item.get("verification_type"))

    def partition_active_control_points(
        self,
        items: list | None,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """Rozdělí aktivní body na dokumentaci, terén a nerozpoznané (po normalizaci)."""
        documentation: list[dict] = []
        terrain: list[dict] = []
        unknown: list[dict] = []
        for item in proverky_knowledge_service.get_active_items(items):
            raw = item.get("verification_type")
            if raw not in (None, "") and str(raw).strip().casefold() not in (
                _DOCUMENTATION_ALIASES | _TERRAIN_ALIASES
            ):
                unknown.append(item)
                logger.warning(
                    "Kontrolní bod %s má nerozpoznaný typ ověření %r.",
                    item.get("id"),
                    raw,
                )
            normalized = self.normalize_verification_type(raw)
            if normalized == VERIFICATION_TYPE_TERRAIN:
                terrain.append(item)
            else:
                documentation.append(item)
        return documentation, terrain, unknown

    def filter_active_control_points(
        self,
        items: list | None,
        *,
        verification_type: str,
    ) -> list[dict]:
        wanted = self.normalize_verification_type(verification_type)
        documentation, terrain, _unknown = self.partition_active_control_points(items)
        if wanted == VERIFICATION_TYPE_TERRAIN:
            return terrain
        return documentation

    def overrides_map(self, inspection_id: int | None) -> dict[tuple[str, str, str], str]:
        if inspection_id is None:
            return {}
        result: dict[tuple[str, str, str], str] = {}
        for row in self.repository.list_for_inspection(inspection_id):
            key = (
                str(row.source_area_id or "").strip(),
                str(row.source_section_id or "").strip(),
                str(row.source_control_point_id or "").strip(),
            )
            result[key] = self.normalize_verification_type(
                row.override_verification_type
            )
        return result

    def effective_verification_type(
        self,
        inspection_id: int | None,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
        methodology_type: str | None = None,
        item: dict | None = None,
        overrides: dict[tuple[str, str, str], str] | None = None,
    ) -> str:
        methodology = (
            self.normalize_verification_type(methodology_type)
            if methodology_type is not None
            else self.methodology_verification_type(item)
        )
        mapping = overrides if overrides is not None else self.overrides_map(inspection_id)
        override = mapping.get(
            (
                str(area_id or "").strip(),
                str(section_id or "").strip(),
                str(control_point_id or "").strip(),
            )
        )
        if override is None:
            return methodology
        return override

    def set_override(
        self,
        inspection_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
        verification_type: str,
        methodology_type: str | None = None,
        item: dict | None = None,
    ) -> str:
        """Nastaví typ ověření pro prověrku. Vrací efektivní typ.

        Pokud odpovídá metodice, výjimku smaže.
        """
        target = self.normalize_verification_type(verification_type)
        methodology = (
            self.normalize_verification_type(methodology_type)
            if methodology_type is not None
            else self.methodology_verification_type(item)
        )
        area = str(area_id or "").strip()
        section = str(section_id or "").strip()
        point = str(control_point_id or "").strip()
        if not inspection_id or not point:
            raise ValueError("Chybí identifikace prověrky nebo kontrolního bodu.")

        if target == methodology:
            self.repository.delete(
                inspection_id,
                area_id=area,
                section_id=section,
                control_point_id=point,
            )
            return methodology

        self.repository.upsert(
            inspection_id,
            area_id=area,
            section_id=section,
            control_point_id=point,
            override_verification_type=target,
        )
        return target

    def list_control_points(
        self,
        inspection_id: int | None = None,
        *,
        verification_type: str | None = None,
    ) -> list[InspectionControlPointRef]:
        """Všechny aktivní kontrolní body metodiky s efektivním typem pro prověrku."""
        wanted = (
            self.normalize_verification_type(verification_type)
            if verification_type is not None
            else None
        )
        overrides = self.overrides_map(inspection_id)
        items: list[InspectionControlPointRef] = []
        for area_node in proverky_knowledge_service.get_knowledge_tree():
            self._collect_from_nodes(
                area_node.children,
                area_id=area_node.area_id,
                area_label=area_node.area_label,
                inspection_id=inspection_id,
                overrides=overrides,
                wanted=wanted,
                sink=items,
            )
        return items

    def _collect_from_nodes(
        self,
        nodes: tuple[KnowledgeTreeNode, ...] | list[KnowledgeTreeNode],
        *,
        area_id: str,
        area_label: str,
        inspection_id: int | None,
        overrides: dict[tuple[str, str, str], str],
        wanted: str | None,
        sink: list[InspectionControlPointRef],
    ) -> None:
        for node in nodes:
            section = node.section
            if isinstance(section, dict):
                section_id = str(section.get("id") or node.node_id or "").strip()
                section_label = str(section.get("nazev") or node.label or "").strip()
                for raw in proverky_knowledge_service.get_active_items(
                    section.get("kontrolni_body")
                ):
                    if not isinstance(raw, dict):
                        continue
                    cp_id = str(raw.get("id") or "").strip()
                    cp_label = str(raw.get("nazev") or "").strip()
                    if not cp_id or not cp_label:
                        continue
                    methodology = self.methodology_verification_type(raw)
                    effective = self.effective_verification_type(
                        inspection_id,
                        area_id=area_id,
                        section_id=section_id,
                        control_point_id=cp_id,
                        methodology_type=methodology,
                        overrides=overrides,
                    )
                    if wanted is not None and effective != wanted:
                        continue
                    sink.append(
                        InspectionControlPointRef(
                            area_id=area_id,
                            area_label=area_label,
                            section_id=section_id,
                            section_label=section_label,
                            control_point_id=cp_id,
                            control_point_label=cp_label,
                            control_point=raw,
                            methodology_verification_type=methodology,
                            effective_verification_type=effective,
                        )
                    )
            if node.children:
                self._collect_from_nodes(
                    node.children,
                    area_id=area_id,
                    area_label=area_label,
                    inspection_id=inspection_id,
                    overrides=overrides,
                    wanted=wanted,
                    sink=sink,
                )


inspection_verification_service = InspectionVerificationService()
