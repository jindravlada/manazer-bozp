from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent, QShowEvent
from PySide6.QtWidgets import QDialog, QLabel, QScrollArea, QVBoxLayout

from core.widgets.dialog_utils import configure_close_button, create_close_box


class ImageViewerDialog(QDialog):
    """Maximalizované okno pro zobrazení fotografie s přizpůsobením velikosti okna."""

    def __init__(self, image_path: Path, *, title: str = "Fotografie", parent=None):
        super().__init__(parent)

        self.setWindowTitle(title)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._original_pixmap = QPixmap(str(image_path))
        if self._original_pixmap.isNull():
            self._original_pixmap = None
            self._image_label.setText("Fotografii se nepodařilo načíst.")

        self._scroll.setWidget(self._image_label)
        layout.addWidget(self._scroll, 1)

        buttons = create_close_box(self)
        configure_close_button(buttons)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._refresh_image()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_image()

    def _refresh_image(self) -> None:
        if self._original_pixmap is None:
            return

        viewport = self._scroll.viewport().size()
        if viewport.width() <= 1 or viewport.height() <= 1:
            return

        scaled = self._original_pixmap.scaled(
            viewport,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)
        self._image_label.setFixedSize(scaled.size())
