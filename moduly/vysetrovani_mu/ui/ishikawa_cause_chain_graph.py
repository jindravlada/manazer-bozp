from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_STATUS_HYPOTEZA,
    ISHIKAWA_STATUS_POTVRZENO,
    ISHIKAWA_STATUS_VYVRACENO,
)
from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_layout import (
    CauseChainGraphLayoutEngine,
    CauseChainLayoutMetrics,
)
from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_model import (
    CauseChainGraphModel,
    CauseChainGraphNode,
    CauseChainLegendEntry,
    build_cause_chain_graph_model,
)
from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_pdf_export import (
    export_cause_chain_graph_to_pdf,
    scene_content_rect,
)


class CauseChainGraphStyle:
    """Styly uzlů a hran podle stavu hypotézy."""

    _STATUS_POTVRZENO = "potvrzeno"
    _STATUS_PRAVDEPODOBNE = "pravdepodobne"
    _STATUS_HYPOTEZA = "hypoteza"
    _STATUS_VYVRACENO = "vyvraceno"
    _STATUS_UNKNOWN = "unknown"

    _FILLS: dict[str, QColor] = {
        _STATUS_POTVRZENO: QColor("#d7eedc"),
        _STATUS_PRAVDEPODOBNE: QColor("#d4ebe4"),
        _STATUS_HYPOTEZA: QColor("#fff6cc"),
        _STATUS_VYVRACENO: QColor("#f8dddd"),
        _STATUS_UNKNOWN: QColor("#ececec"),
    }

    _BORDERS: dict[str, QColor] = {
        _STATUS_POTVRZENO: QColor("#7cb587"),
        _STATUS_PRAVDEPODOBNE: QColor("#7eb8aa"),
        _STATUS_HYPOTEZA: QColor("#d9c86a"),
        _STATUS_VYVRACENO: QColor("#d99292"),
        _STATUS_UNKNOWN: QColor("#b8b8b8"),
    }

    _ALIASES: dict[str, str] = {
        ISHIKAWA_STATUS_POTVRZENO: _STATUS_POTVRZENO,
        "potvrzena": _STATUS_POTVRZENO,
        "potvrzená": _STATUS_POTVRZENO,
        "confirmed": _STATUS_POTVRZENO,
        _STATUS_PRAVDEPODOBNE: _STATUS_PRAVDEPODOBNE,
        "pravdepodobna": _STATUS_PRAVDEPODOBNE,
        "pravděpodobná": _STATUS_PRAVDEPODOBNE,
        "pravděpodobné": _STATUS_PRAVDEPODOBNE,
        ISHIKAWA_STATUS_HYPOTEZA: _STATUS_HYPOTEZA,
        "hypotéza": _STATUS_HYPOTEZA,
        "otevrena": _STATUS_HYPOTEZA,
        "otevřená": _STATUS_HYPOTEZA,
        "open": _STATUS_HYPOTEZA,
        ISHIKAWA_STATUS_VYVRACENO: _STATUS_VYVRACENO,
        "vyvracena": _STATUS_VYVRACENO,
        "vyvrácena": _STATUS_VYVRACENO,
        "vyvráceno": _STATUS_VYVRACENO,
    }

    def __init__(self, metrics: CauseChainLayoutMetrics | None = None):
        self._metrics = metrics or CauseChainLayoutMetrics()

    @property
    def corner_radius(self) -> float:
        return self._metrics.corner_radius

    @classmethod
    def legend_entries(cls) -> list[CauseChainLegendEntry]:
        return [
            CauseChainLegendEntry(cls._FILLS[cls._STATUS_POTVRZENO], "potvrzeno"),
            CauseChainLegendEntry(cls._FILLS[cls._STATUS_HYPOTEZA], "hypotéza / otevřeno"),
            CauseChainLegendEntry(cls._FILLS[cls._STATUS_VYVRACENO], "vyvráceno"),
        ]

    def resolve_status(self, node: CauseChainGraphNode) -> str:
        raw = str(node.cause.get("status") or "").strip().lower()
        if not raw:
            return self._STATUS_UNKNOWN
        return self._ALIASES.get(raw, self._STATUS_UNKNOWN)

    def node_fill(self, node: CauseChainGraphNode) -> QBrush:
        status = self.resolve_status(node)
        return QBrush(self._FILLS.get(status, self._FILLS[self._STATUS_UNKNOWN]))

    def node_border(self, node: CauseChainGraphNode) -> QPen:
        status = self.resolve_status(node)
        color = self._BORDERS.get(status, self._BORDERS[self._STATUS_UNKNOWN])
        return QPen(color, 1.5)

    def node_text_color(self, node: CauseChainGraphNode) -> QColor:
        _ = node
        return QColor("#1f1f1f")

    def edge_pen(self) -> QPen:
        return QPen(QColor("#666666"), 1.5)


class CauseChainNodeGraphicsItem(QGraphicsItem):
    """Grafický uzel – připraveno pro kliknutí a metodickou kartu."""

    def __init__(self, node: CauseChainGraphNode, style: CauseChainGraphStyle, rect):
        super().__init__()
        self.node = node
        self._style = style
        self._rect = rect
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def boundingRect(self):
        return self._rect

    def paint(self, painter: QPainter, option, widget=None) -> None:
        _ = option, widget
        path = QPainterPath()
        path.addRoundedRect(self._rect, self._style.corner_radius, self._style.corner_radius)
        painter.setPen(self._style.node_border(self.node))
        painter.setBrush(self._style.node_fill(self.node))
        painter.drawPath(path)

        painter.setPen(self._style.node_text_color(self.node))
        painter.drawText(
            self._rect,
            Qt.AlignmentFlag.AlignCenter,
            self.node.label,
        )


class CauseChainEdgeGraphicsItem(QGraphicsPathItem):
    """Spojení mezi uzly se šipkou směrem dolů."""

    def __init__(self, start: QPointF, end: QPointF, style: CauseChainGraphStyle):
        super().__init__()
        self.setPen(style.edge_pen())
        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(end)

        arrow_size = 8.0
        arrow = QPainterPath()
        arrow.moveTo(end)
        arrow.lineTo(end.x() - arrow_size, end.y() - arrow_size)
        arrow.lineTo(end.x() + arrow_size, end.y() - arrow_size)
        arrow.closeSubpath()
        path.addPath(arrow)
        self.setPath(path)


class CauseChainGraphSceneFactory:
    """Sestavení scény z modelu – odděleno pro budoucí export a interaktivitu."""

    def __init__(
        self,
        layout_engine: CauseChainGraphLayoutEngine | None = None,
        style: CauseChainGraphStyle | None = None,
    ):
        metrics = CauseChainLayoutMetrics()
        self._layout_engine = layout_engine or CauseChainGraphLayoutEngine(metrics)
        self._style = style or CauseChainGraphStyle(metrics)

    def create_scene(self, model: CauseChainGraphModel) -> QGraphicsScene:
        scene = QGraphicsScene()
        if not model.is_renderable:
            return scene

        layout = self._layout_engine.layout(model)
        node_items: dict[str, CauseChainNodeGraphicsItem] = {}

        for cause_id, layout_node in layout.nodes.items():
            item = CauseChainNodeGraphicsItem(
                model.nodes[cause_id],
                self._style,
                layout_node.rect,
            )
            scene.addItem(item)
            node_items[cause_id] = item

        for edge in model.edges:
            parent_item = node_items.get(edge.parent_id)
            child_item = node_items.get(edge.child_id)
            if parent_item is None or child_item is None:
                continue
            start = QPointF(
                parent_item.boundingRect().center().x(),
                parent_item.boundingRect().bottom(),
            )
            end = QPointF(
                child_item.boundingRect().center().x(),
                child_item.boundingRect().top(),
            )
            edge_item = CauseChainEdgeGraphicsItem(start, end, self._style)
            scene.addItem(edge_item)
            edge_item.stackBefore(parent_item)

        content_rect = scene_content_rect(scene)
        if not content_rect.isNull():
            scene.setSceneRect(content_rect)
        return scene


class CauseChainGraphView(QGraphicsView):
    """Zobrazení grafu – připraveno pro zoom a export."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def show_scene(self, scene: QGraphicsScene) -> None:
        self.setScene(scene)
        if not scene.sceneRect().isNull():
            self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class CauseChainGraphLegendWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        title = QLabel("Legenda:")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        for entry in CauseChainGraphStyle.legend_entries():
            row = QHBoxLayout()
            swatch = QLabel()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(
                "background-color: {bg}; border: 1px solid {border}; border-radius: 3px;".format(
                    bg=entry.fill.name(),
                    border=entry.fill.darker(115).name(),
                )
            )
            label = QLabel(entry.label)
            row.addWidget(swatch)
            row.addWidget(label)
            row.addStretch()
            layout.addLayout(row)


class MuIshikawaChainGraphWidget(QWidget):
    """Kontejner grafu s fallbackem pro neplatná data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_factory = CauseChainGraphSceneFactory()
        self._model: CauseChainGraphModel | None = None
        self._message_label = QLabel()
        self._message_label.setWordWrap(True)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._warning_label = QLabel()
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        self._warning_label.setStyleSheet(
            "color: #8a4b00; background: #fff4e5; border: 1px solid #f0c987; "
            "border-radius: 4px; padding: 8px;"
        )

        self._graph_view = CauseChainGraphView()
        self._legend = CauseChainGraphLegendWidget()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._warning_label)
        layout.addWidget(self._message_label)
        layout.addWidget(self._graph_view, stretch=1)
        layout.addWidget(self._legend)

    def set_causes(self, causes: list[dict], *, warning_text: str = "") -> None:
        self._warning_label.setText(warning_text)
        self._warning_label.setVisible(bool(warning_text))

        self._model = build_cause_chain_graph_model(causes)
        if not self._model.is_renderable:
            self._message_label.setText(self._model.message or "")
            self._message_label.setVisible(True)
            self._graph_view.hide()
            self._legend.hide()
            self._graph_view.setScene(None)
            return

        self._message_label.hide()
        self._graph_view.show()
        self._legend.show()
        scene = self._scene_factory.create_scene(self._model)
        self._graph_view.show_scene(scene)

    def can_export_to_pdf(self) -> bool:
        return self._model is not None and self._model.is_renderable

    def export_message(self) -> str:
        if self._model is None or self._model.is_renderable:
            return ""
        return self._model.message or "Graf řetězce příčin nelze exportovat."

    def export_to_pdf(self, path: str) -> bool:
        if not self.can_export_to_pdf() or self._model is None:
            return False
        return export_cause_chain_graph_to_pdf(
            self._model,
            path,
            style=CauseChainGraphStyle(),
            legend_entries=CauseChainGraphStyle.legend_entries(),
        )

    def refit(self) -> None:
        scene = self._graph_view.scene()
        if scene is not None:
            bounds = scene.itemsBoundingRect()
            if not bounds.isNull():
                self._graph_view.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)
                return
            if not scene.sceneRect().isNull():
                self._graph_view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.refit()
