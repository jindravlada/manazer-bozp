"""Jeden obrázek otázky nebo odpovědi: výběr, náhled, odebrání.

Nový soubor zůstane na původní cestě, dokud se editor neuloží.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from core.ui.photo_picker_dialog import PhotoPickerDialog
from moduly.testy.constants import MODULE_NAME
from moduly.testy.sluzby.written_image_normalizer import (
    WrittenImageError,
    assert_input_within_limit,
)


class WrittenQuestionImageSlot(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_path: str | None = None
        self._attachment_id: int | None = None
        self._removed = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.preview = QLabel("Bez obrázku")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(96, 72)
        self.preview.setStyleSheet("border: 1px solid palette(mid);")

        buttons = QVBoxLayout()
        self.pick_btn = QPushButton("Vybrat")
        self.remove_btn = QPushButton("Odebrat")
        self.remove_btn.setEnabled(False)
        buttons.addWidget(self.pick_btn)
        buttons.addWidget(self.remove_btn)
        buttons.addStretch()

        layout.addWidget(self.preview)
        layout.addLayout(buttons)
        layout.addStretch()

        self.pick_btn.clicked.connect(self.pick)
        self.remove_btn.clicked.connect(self.remove)

    def pick(self) -> None:
        selected = PhotoPickerDialog.get_photo(parent=self)
        if selected is None:
            return
        self.set_source_path(str(selected))

    def set_source_path(self, path: str) -> None:
        candidate = Path(path)
        try:
            assert_input_within_limit(candidate)
        except WrittenImageError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        self._source_path = path
        self._removed = False
        self._show_preview(candidate)
        self._refresh_buttons()
        self.changed.emit()

    def remove(self) -> None:
        self._source_path = None
        self._removed = True
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Bez obrázku")
        self._refresh_buttons()
        self.changed.emit()

    def clear(self) -> None:
        self._source_path = None
        self._attachment_id = None
        self._removed = False
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Bez obrázku")
        self._refresh_buttons()

    def set_saved(self, attachment_id: int | None, path: Path | None) -> None:
        self._source_path = None
        self._removed = False
        self._attachment_id = int(attachment_id) if attachment_id else None
        if path is not None and path.is_file():
            self._show_preview(path)
        else:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Bez obrázku" if not attachment_id else "Náhled není dostupný")
        self._refresh_buttons()

    def has_content(self) -> bool:
        if self._source_path:
            return True
        return bool(self._attachment_id) and not self._removed

    def source_path(self) -> str | None:
        return self._source_path

    def keep_attachment_id(self) -> int | None:
        if self._source_path or self._removed:
            return None
        return self._attachment_id

    def _show_preview(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Náhled není dostupný")
            return
        self.preview.setText("")
        self.preview.setPixmap(
            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _refresh_buttons(self) -> None:
        filled = self.has_content()
        self.pick_btn.setText("Změnit" if filled else "Vybrat")
        self.remove_btn.setEnabled(filled)
