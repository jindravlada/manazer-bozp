from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QColor

from moduly.vysetrovani_mu.ui.ishikawa_cause_chain import (
    build_cause_chain_structure,
    chain_cause_label,
    has_cause_chain_cycle,
)


@dataclass(frozen=True)
class CauseChainLegendEntry:
    fill: QColor
    label: str


@dataclass(frozen=True)
class CauseChainGraphNode:
    cause_id: str
    label: str
    cause: dict


@dataclass(frozen=True)
class CauseChainGraphEdge:
    parent_id: str
    child_id: str


@dataclass
class CauseChainGraphModel:
    nodes: dict[str, CauseChainGraphNode] = field(default_factory=dict)
    edges: list[CauseChainGraphEdge] = field(default_factory=list)
    roots: list[str] = field(default_factory=list)
    message: str | None = None
    has_cycle: bool = False

    @property
    def is_renderable(self) -> bool:
        return not self.message and bool(self.nodes)


def build_cause_chain_graph_model(causes: list[dict]) -> CauseChainGraphModel:
    if not causes:
        return CauseChainGraphModel(
            message="Zatím nejsou definovány žádné příčiny.",
        )

    if has_cause_chain_cycle(causes):
        return CauseChainGraphModel(
            has_cycle=True,
            message="⚠ Zjištěna neplatná cyklická vazba mezi příčinami.",
        )

    structure = build_cause_chain_structure(causes)
    if structure is None:
        return CauseChainGraphModel(
            message="Zatím nejsou definovány žádné příčiny.",
        )

    nodes = {
        cause_id: CauseChainGraphNode(
            cause_id=cause_id,
            label=chain_cause_label(cause),
            cause=cause,
        )
        for cause_id, cause in structure.by_id.items()
    }
    edges = [
        CauseChainGraphEdge(parent_id=parent_id, child_id=child_id)
        for parent_id, child_ids in structure.children.items()
        for child_id in child_ids
    ]

    return CauseChainGraphModel(
        nodes=nodes,
        edges=edges,
        roots=list(structure.roots),
    )
