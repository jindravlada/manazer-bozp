"""Dialog s doporučeným postupem kontroly (modální s překryvem editoru)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_close_button, create_close_box
from moduly.proverky.constants import (
    KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT,
    KNOWLEDGE_CONTROL_PROCEDURE_DIALOG_TITLE,
)
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service

_DIALOG_WIDTH = 700
_DIALOG_HEIGHT = 450
_SECTION_TO_CONTENT_SPACING = 12

# ~43 % neprůhlednosti – podklad zůstane rozpoznatelný, dialog dominantní.
_OVERLAY_ALPHA = 110
_OVERLAY_OBJECT_NAME = "ProverkyControlProcedureDimOverlay"


class ParentDimOverlay(QWidget):
    """Poloprůhledný šedý překryv nad podkladovým editorem."""

    def __init__(self, host: QWidget):
        super().__init__(host)
        self.setObjectName(_OVERLAY_OBJECT_NAME)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(False)
        self._sync_geometry()
        host.installEventFilter(self)
        self.raise_()
        self.show()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.parentWidget() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
        ):
            self._sync_geometry()
        return False

    def _sync_geometry(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, _OVERLAY_ALPHA))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        event.accept()

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.accept()


def find_dim_overlays(host: QWidget | None) -> list[ParentDimOverlay]:
    if host is None:
        return []
    return [
        child
        for child in host.findChildren(ParentDimOverlay)
        if child.objectName() == _OVERLAY_OBJECT_NAME
    ]


def clear_dim_overlays(host: QWidget | None) -> None:
    for overlay in find_dim_overlays(host):
        parent = overlay.parentWidget()
        if parent is not None:
            parent.removeEventFilter(overlay)
        overlay.hide()
        overlay.setParent(None)
        overlay.deleteLater()


class ProverkyControlProcedureDialog(QDialog):
    """Modální okno s doporučeným postupem kontroly a překryvem editoru."""

    def __init__(self, section: dict, *, section_label: str = "", parent=None):
        super().__init__(parent)

        self.setWindowTitle(KNOWLEDGE_CONTROL_PROCEDURE_DIALOG_TITLE)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.resize(_DIALOG_WIDTH, _DIALOG_HEIGHT)

        self._overlay: ParentDimOverlay | None = None
        self._overlay_host: QWidget | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        self._section_title_label = QLabel()
        self._section_title_label.setObjectName("SectionTitle")
        self._section_title_label.setWordWrap(True)
        root_layout.addWidget(self._section_title_label)
        root_layout.addSpacing(_SECTION_TO_CONTENT_SPACING)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        self._content_layout.setSpacing(12)
        scroll.setWidget(self._content_host)

        root_layout.addWidget(scroll, 1)

        buttons = create_close_box(self)
        configure_close_button(buttons)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

        self.finished.connect(self._cleanup_overlay)
        self.destroyed.connect(self._on_destroyed)

        self.set_section(section, section_label=section_label)

    def overlay_host(self) -> QWidget | None:
        """Podkladové okno/editor, nad nímž se zobrazí překryv."""
        parent = self.parentWidget()
        if parent is None:
            return None
        window = parent.window()
        return window if window is not None else parent

    def active_overlay(self) -> ParentDimOverlay | None:
        return self._overlay

    def _ensure_overlay(self) -> None:
        host = self.overlay_host()
        if host is None:
            return
        clear_dim_overlays(host)
        self._overlay_host = host
        self._overlay = ParentDimOverlay(host)
        self._overlay.raise_()

    def _cleanup_overlay(self, *_args) -> None:
        host = self._overlay_host
        if self._overlay is not None:
            parent = self._overlay.parentWidget()
            if parent is not None:
                parent.removeEventFilter(self._overlay)
            self._overlay.hide()
            self._overlay.setParent(None)
            self._overlay.deleteLater()
            self._overlay = None
        if host is not None:
            clear_dim_overlays(host)
        self._overlay_host = None

    def _on_destroyed(self, *_args) -> None:
        self._cleanup_overlay()

    def exec(self) -> int:  # noqa: A003
        self._ensure_overlay()
        try:
            return super().exec()
        finally:
            self._cleanup_overlay()

    def set_section(self, section: dict, *, section_label: str = "") -> None:
        label = section_label.strip() or str(section.get("nazev") or "").strip()
        if label:
            self._section_title_label.setText(label)
            self._section_title_label.setVisible(True)
        else:
            self._section_title_label.clear()
            self._section_title_label.setVisible(False)

        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        intro = str(section.get("postup_kontroly_uvod") or "").strip()
        if intro:
            intro_label = QLabel(intro)
            intro_label.setWordWrap(True)
            self._content_layout.addWidget(intro_label)

        items = proverky_knowledge_service.get_active_items(section.get("postup_kontroly"))
        if not items:
            empty = QLabel(KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT)
            empty.setObjectName("InfoText")
            empty.setWordWrap(True)
            self._content_layout.addWidget(empty)
        else:
            for index, item in enumerate(items, start=1):
                text = str(item.get("text") or "—").strip() or "—"
                step_label = QLabel(f"{index}. {text}")
                step_label.setWordWrap(True)
                self._content_layout.addWidget(step_label)

        self._content_layout.addStretch()
