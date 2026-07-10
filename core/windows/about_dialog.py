"""Dialog O programu."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from core.version import app_about_text, app_display_name


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"O programu – {app_display_name()}")

        layout = QVBoxLayout(self)

        message = QLabel(app_about_text())
        message.setWordWrap(True)
        layout.addWidget(message)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
