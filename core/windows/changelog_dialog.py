"""Dialog pro zobrazení historie verzí."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.help.changelog_service import load_changelog_text


class ChangelogDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Historie verzí")
        self.resize(900, 700)

        layout = QVBoxLayout(self)

        viewer = QPlainTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(load_changelog_text())
        layout.addWidget(viewer)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
