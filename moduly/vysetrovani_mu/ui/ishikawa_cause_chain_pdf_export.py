from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPainter, QPainterPath, QPdfWriter, QPen

from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_layout import (
    CauseChainGraphLayout,
    CauseChainGraphLayoutEngine,
    CauseChainLayoutMetrics,
    CauseChainNodeLayout,
)
from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_model import (
    CauseChainGraphModel,
    CauseChainLegendEntry,
)

PDF_RESOLUTION = 72
PDF_BASE_FONT_SIZE = 11.0
PDF_MIN_FONT_SIZE = 8.0
PDF_MARGIN_MM = 18.0


def _mm_to_pt(mm: float) -> float:
    return mm / 25.4 * PDF_RESOLUTION


class CauseChainPdfRenderer:
    """Samostatný tiskový renderer grafu – bez QGraphicsScene."""

    def __init__(self, style=None):
        self._style = style

    def _graph_style(self):
        if self._style is None:
            from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_graph import CauseChainGraphStyle

            self._style = CauseChainGraphStyle()
        return self._style

    def render(
        self,
        model: CauseChainGraphModel,
        path: str,
        *,
        legend_entries: list[CauseChainLegendEntry],
        title: str = "Řetězec příčin",
    ) -> bool:
        if not model.is_renderable:
            return False

        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        writer.setResolution(PDF_RESOLUTION)

        painter = QPainter(writer)
        if not painter.isActive():
            return False

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        margin = _mm_to_pt(PDF_MARGIN_MM)
        page_rect = QRectF(writer.pageLayout().paintRectPixels(PDF_RESOLUTION))
        content = page_rect.adjusted(margin, margin, -margin, -margin)

        title_height = self._draw_title(painter, content, title)
        legend_height = self._legend_block_height(len(legend_entries))
        section_gap = 6.0
        graph_area = QRectF(
            content.left(),
            content.top() + title_height + section_gap,
            content.width(),
            max(content.height() - title_height - legend_height - section_gap * 2, 80),
        )
        legend_area = QRectF(
            content.left(),
            graph_area.bottom() + section_gap,
            content.width(),
            content.bottom() - graph_area.bottom() - section_gap,
        )

        layout, font_size, scale = self._fit_layout(model, graph_area)
        if layout is None:
            painter.end()
            return False

        font = self._node_font(font_size)
        painter.setFont(font)
        self._draw_edges(painter, model, layout, scale)
        self._draw_nodes(painter, model, layout, font, scale)
        self._draw_legend(painter, legend_area, legend_entries)

        painter.end()
        return True

    def _fit_layout(
        self,
        model: CauseChainGraphModel,
        graph_area: QRectF,
    ) -> tuple[CauseChainGraphLayout | None, float, float]:
        base_font_size = PDF_BASE_FONT_SIZE
        layout = self._layout_engine(base_font_size).layout(model)
        bounds = self._layout_bounds(layout)
        if bounds.isNull():
            return None, PDF_MIN_FONT_SIZE, 1.0

        scale = min(
            graph_area.width() / bounds.width(),
            graph_area.height() / bounds.height(),
        )
        if base_font_size * scale < PDF_MIN_FONT_SIZE:
            scale = PDF_MIN_FONT_SIZE / base_font_size

        scaled_bounds = QRectF(
            0,
            0,
            bounds.width() * scale,
            bounds.height() * scale,
        )
        offset = QPointF(
            graph_area.left() + (graph_area.width() - scaled_bounds.width()) / 2 - bounds.left() * scale,
            graph_area.top() + (graph_area.height() - scaled_bounds.height()) / 2 - bounds.top() * scale,
        )
        return self._scale_layout(layout, scale, offset), base_font_size * scale, scale

    def _scale_layout(
        self,
        layout: CauseChainGraphLayout,
        scale: float,
        offset: QPointF,
    ) -> CauseChainGraphLayout:
        nodes: dict[str, CauseChainNodeLayout] = {}
        for cause_id, node in layout.nodes.items():
            rect = node.rect
            nodes[cause_id] = CauseChainNodeLayout(
                cause_id=cause_id,
                rect=QRectF(
                    rect.left() * scale + offset.x(),
                    rect.top() * scale + offset.y(),
                    rect.width() * scale,
                    rect.height() * scale,
                ),
                lines=node.lines,
            )
        scene_rect = self._layout_bounds(layout)
        scene_rect = QRectF(
            scene_rect.left() * scale + offset.x(),
            scene_rect.top() * scale + offset.y(),
            scene_rect.width() * scale,
            scene_rect.height() * scale,
        )
        return CauseChainGraphLayout(nodes=nodes, scene_rect=scene_rect)

    def _layout_engine(self, font_size: float) -> CauseChainGraphLayoutEngine:
        font = self._node_font(font_size)
        return CauseChainGraphLayoutEngine(
            metrics=CauseChainLayoutMetrics(),
            font=font,
        )

    @staticmethod
    def _node_font(font_size: float) -> QFont:
        font = QFont()
        font.setPointSizeF(max(font_size, 7.0))
        return font

    @staticmethod
    def _layout_bounds(layout: CauseChainGraphLayout) -> QRectF:
        bounds = QRectF()
        for node in layout.nodes.values():
            bounds = bounds.united(node.rect)
        return bounds

    def _draw_title(self, painter: QPainter, content: QRectF, title: str) -> float:
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSizeF(14)
        painter.setFont(title_font)
        title_height = 24.0
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(
            QRectF(content.left(), content.top(), content.width(), title_height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title,
        )
        return title_height

    def _draw_nodes(
        self,
        painter: QPainter,
        model: CauseChainGraphModel,
        layout: CauseChainGraphLayout,
        font: QFont,
        scale: float,
    ) -> None:
        metrics_cfg = CauseChainLayoutMetrics()
        painter.setFont(font)
        metrics = painter.fontMetrics()
        line_height = metrics.height()
        radius = metrics_cfg.corner_radius * scale
        pad_h = metrics_cfg.node_horizontal_padding * scale
        pad_v = metrics_cfg.node_vertical_padding * scale

        for cause_id, node_layout in layout.nodes.items():
            graph_node = model.nodes[cause_id]
            rect = node_layout.rect
            lines = node_layout.lines or (graph_node.label,)

            path = QPainterPath()
            path.addRoundedRect(rect, radius, radius)
            painter.setPen(self._graph_style().node_border(graph_node))
            painter.setBrush(self._graph_style().node_fill(graph_node))
            painter.drawPath(path)

            text_rect = rect.adjusted(pad_h, pad_v, -pad_h, -pad_v)
            text_top = text_rect.top() + max(
                0,
                (text_rect.height() - line_height * len(lines)) / 2,
            )
            painter.setPen(self._graph_style().node_text_color(graph_node))
            for index, line in enumerate(lines):
                line_rect = QRectF(
                    text_rect.left(),
                    text_top + index * line_height,
                    text_rect.width(),
                    line_height,
                )
                painter.drawText(
                    line_rect,
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                    line,
                )

    def _draw_edges(
        self,
        painter: QPainter,
        model: CauseChainGraphModel,
        layout: CauseChainGraphLayout,
        scale: float,
    ) -> None:
        edge_pen = self._graph_style().edge_pen()
        scaled_pen = edge_pen
        if scale != 1.0:
            scaled_pen = QPen(edge_pen)
            scaled_pen.setWidthF(max(edge_pen.widthF() * scale, 1.0))
        painter.setPen(scaled_pen)
        painter.setBrush(Qt.GlobalColor.transparent)

        for edge in model.edges:
            parent = layout.nodes.get(edge.parent_id)
            child = layout.nodes.get(edge.child_id)
            if parent is None or child is None:
                continue

            parent_rect = parent.rect
            child_rect = child.rect
            start = QPointF(parent_rect.center().x(), parent_rect.bottom())
            end = QPointF(child_rect.center().x(), child_rect.top())

            painter.drawLine(start, end)

            arrow_size = 5.0 * scale
            arrow = QPainterPath()
            arrow.moveTo(end)
            arrow.lineTo(end.x() - arrow_size, end.y() - arrow_size)
            arrow.lineTo(end.x() + arrow_size, end.y() - arrow_size)
            arrow.closeSubpath()
            painter.fillPath(arrow, scaled_pen.color())

    def _legend_block_height(self, entry_count: int) -> float:
        return 24 + max(entry_count, 1) * 16

    def _draw_legend(
        self,
        painter: QPainter,
        rect: QRectF,
        legend_entries: list[CauseChainLegendEntry],
    ) -> None:
        if not legend_entries:
            return

        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSizeF(10)
        painter.setFont(title_font)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(
            QRectF(rect.left(), rect.top(), rect.width(), 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Legenda:",
        )

        body_font = QFont()
        body_font.setPointSizeF(9)
        painter.setFont(body_font)
        metrics = painter.fontMetrics()

        y = rect.top() + 20
        swatch_size = 10.0
        gap = 6.0
        for entry in legend_entries:
            swatch_rect = QRectF(rect.left(), y, swatch_size, swatch_size)
            painter.setPen(entry.fill.darker(115))
            painter.setBrush(entry.fill)
            painter.drawRoundedRect(swatch_rect, 2, 2)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(
                QRectF(swatch_rect.right() + gap, y - 1, rect.width(), swatch_size + 2),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                entry.label,
            )
            y += max(metrics.height(), swatch_size) + 4


def export_cause_chain_graph_to_pdf(
    model: CauseChainGraphModel,
    path: str,
    *,
    style=None,
    legend_entries: list[CauseChainLegendEntry],
    title: str = "Řetězec příčin",
) -> bool:
    return CauseChainPdfRenderer(style=style).render(
        model,
        path,
        legend_entries=legend_entries,
        title=title,
    )


def scene_content_rect(scene) -> QRectF:
    """Pomocná funkce pro zobrazení na obrazovce – ne pro PDF."""
    bounds = scene.itemsBoundingRect()
    if bounds.isNull():
        bounds = scene.sceneRect()
    if bounds.isNull():
        return QRectF()
    padding = 24.0
    return bounds.adjusted(-padding, -padding, padding, padding)
