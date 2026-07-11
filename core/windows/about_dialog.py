"""Dialog O programu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.version import APP_AUTHOR, APP_COPYRIGHT, app_display_name


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"O programu – {app_display_name()}")
        self.setMinimumSize(540, 280)
        self.resize(560, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(10)

        title = QLabel(app_display_name())
        title.setObjectName("AboutTitle")
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #174a8b;")

        author = QLabel(APP_AUTHOR)
        author.setObjectName("AboutAuthor")
        author.setWordWrap(True)

        copyright_label = QLabel(APP_COPYRIGHT)
        copyright_label.setObjectName("AboutCopyright")
        copyright_label.setWordWrap(True)
        copyright_label.setStyleSheet("color: #555;")

        layout.addWidget(title)
        layout.addSpacing(6)
        layout.addWidget(author)
        layout.addWidget(copyright_label)
        layout.addStretch(1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box, 0, Qt.AlignmentFlag.AlignRight)
