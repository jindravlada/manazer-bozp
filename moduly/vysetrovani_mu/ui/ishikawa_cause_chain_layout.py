from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSizeF
from PySide6.QtGui import QFont, QFontMetrics

from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_model import CauseChainGraphModel


@dataclass(frozen=True)
class CauseChainLayoutMetrics:
    node_horizontal_padding: float = 16.0
    node_vertical_padding: float = 10.0
    sibling_gap: float = 40.0
    level_gap: float = 60.0
    tree_gap: float = 80.0
    corner_radius: float = 8.0


@dataclass(frozen=True)
class CauseChainNodeLayout:
    cause_id: str
    rect: QRectF
    lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class CauseChainGraphLayout:
    nodes: dict[str, CauseChainNodeLayout]
    scene_rect: QRectF


class CauseChainGraphLayoutEngine:
    """Výpočet automatického rozvržení stromu shora dolů.

    Budoucí rozšíření: složitější stromy, horizontální režim, kolize s metodickými panely.
    """

    def __init__(
        self,
        metrics: CauseChainLayoutMetrics | None = None,
        *,
        font: QFont | None = None,
        max_node_text_width: float | None = None,
    ):
        self._metrics = metrics or CauseChainLayoutMetrics()
        self._font = font or QFont()
        self._font_metrics = QFontMetrics(self._font)
        self._max_node_text_width = max_node_text_width

    def layout(self, model: CauseChainGraphModel) -> CauseChainGraphLayout:
        node_layouts = self._measure_nodes(model)
        node_sizes = {cause_id: layout.size for cause_id, layout in node_layouts.items()}
        node_lines = {cause_id: layout.lines for cause_id, layout in node_layouts.items()}
        children = self._children_map(model)
        positions: dict[str, CauseChainNodeLayout] = {}
        cursor_x = 0.0

        for root_id in model.roots:
            subtree_width = self._subtree_width(root_id, children, node_sizes)
            self._assign_subtree(
                root_id,
                children,
                node_sizes,
                node_lines,
                positions,
                x_center=cursor_x + subtree_width / 2,
                depth=0,
            )
            cursor_x += subtree_width + self._metrics.tree_gap

        if not positions:
            return CauseChainGraphLayout(nodes={}, scene_rect=QRectF(0, 0, 0, 0))

        scene_rect = QRectF()
        for layout_node in positions.values():
            scene_rect = scene_rect.united(layout_node.rect)
        scene_rect = scene_rect.adjusted(-40, -40, 40, 40)
        return CauseChainGraphLayout(nodes=positions, scene_rect=scene_rect)

    @dataclass(frozen=True)
    class _MeasuredNode:
        size: QSizeF
        lines: tuple[str, ...]

    def _measure_nodes(self, model: CauseChainGraphModel) -> dict[str, _MeasuredNode]:
        return {
            cause_id: self._measure_node(node.label)
            for cause_id, node in model.nodes.items()
        }

    def _measure_node(self, label: str) -> _MeasuredNode:
        lines = tuple(self._wrap_label(label))
        line_height = self._font_metrics.height()
        text_block_height = max(line_height * len(lines), line_height)
        max_line_width = max(
            (self._font_metrics.horizontalAdvance(line) for line in lines),
            default=0,
        )
        width = max_line_width + self._metrics.node_horizontal_padding * 2
        if self._max_node_text_width is not None:
            width = min(max(width, 40.0), self._max_node_text_width)
        height = text_block_height + self._metrics.node_vertical_padding * 2
        return self._MeasuredNode(size=QSizeF(width, height), lines=lines)

    def _wrap_label(self, label: str) -> list[str]:
        text = label.strip() or "—"
        if self._max_node_text_width is None:
            return [text]

        max_text_width = self._max_node_text_width - self._metrics.node_horizontal_padding * 2
        if max_text_width <= 0:
            return [self._truncate_line(text, 24)]

        words = text.split()
        if not words:
            return [self._truncate_line(text, max_text_width)]

        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if self._font_metrics.horizontalAdvance(candidate) <= max_text_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            if self._font_metrics.horizontalAdvance(word) <= max_text_width:
                current = word
            else:
                lines.append(self._truncate_line(word, max_text_width))
                current = ""
        if current:
            lines.append(current)
        return lines or [self._truncate_line(text, max_text_width)]

    def _truncate_line(self, text: str, max_width: float) -> str:
        if self._font_metrics.horizontalAdvance(text) <= max_width:
            return text
        ellipsis = "…"
        value = text
        while value and self._font_metrics.horizontalAdvance(value + ellipsis) > max_width:
            value = value[:-1]
        return (value + ellipsis) if value else ellipsis

    def _children_map(self, model: CauseChainGraphModel) -> dict[str, list[str]]:
        children: dict[str, list[str]] = {cause_id: [] for cause_id in model.nodes}
        for edge in model.edges:
            children.setdefault(edge.parent_id, []).append(edge.child_id)
        return children

    def _subtree_width(
        self,
        node_id: str,
        children: dict[str, list[str]],
        node_sizes: dict[str, QSizeF],
    ) -> float:
        child_ids = children.get(node_id, [])
        if not child_ids:
            return node_sizes[node_id].width()

        widths = [self._subtree_width(child_id, children, node_sizes) for child_id in child_ids]
        return sum(widths) + self._metrics.sibling_gap * max(len(child_ids) - 1, 0)

    def _assign_subtree(
        self,
        node_id: str,
        children: dict[str, list[str]],
        node_sizes: dict[str, QSizeF],
        node_lines: dict[str, tuple[str, ...]],
        positions: dict[str, CauseChainNodeLayout],
        *,
        x_center: float,
        depth: int,
    ) -> None:
        size = node_sizes[node_id]
        y = depth * (size.height() + self._metrics.level_gap)
        rect = QRectF(x_center - size.width() / 2, y, size.width(), size.height())
        positions[node_id] = CauseChainNodeLayout(
            cause_id=node_id,
            rect=rect,
            lines=node_lines.get(node_id, ()),
        )

        child_ids = children.get(node_id, [])
        if not child_ids:
            return

        subtree_width = self._subtree_width(node_id, children, node_sizes)
        child_x = x_center - subtree_width / 2
        for child_id in child_ids:
            child_subtree_width = self._subtree_width(child_id, children, node_sizes)
            self._assign_subtree(
                child_id,
                children,
                node_sizes,
                node_lines,
                positions,
                x_center=child_x + child_subtree_width / 2,
                depth=depth + 1,
            )
            child_x += child_subtree_width + self._metrics.sibling_gap
