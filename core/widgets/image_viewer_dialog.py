from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QScrollArea, QVBoxLayout


class ImageViewerDialog(QDialog):
    """Jednoduché okno pro zobrazení fotografie."""

    def __init__(self, image_path: Path, *, title: str = "Fotografie", parent=None):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(960, 720)

        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            label.setText("Fotografii se nepodařilo načíst.")
        else:
            label.setPixmap(pixmap)

        scroll.setWidget(label)
        layout.addWidget(scroll)
