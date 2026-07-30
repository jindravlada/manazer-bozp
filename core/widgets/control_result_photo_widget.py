"""Fotografie u výsledku kontroly kontrolního bodu."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.services.control_result_photo_service import control_result_photo_service
from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
from core.ui.photo_picker_dialog import PhotoPickerDialog
from core.widgets.dialog_utils import exec_maximized
from core.widgets.image_viewer_dialog import ImageViewerDialog

PHOTO_SECTION_LABEL = "Fotografie"
PHOTO_ADD_LABEL = "📷 Přidat fotografii"
PHOTO_REMOVE_LABEL = "🗑 Odebrat"
PHOTO_VIEW_LABEL = "🔍 Náhled"


class _ClickablePhotoLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ControlResultPhotoWidget(QWidget):
    photo_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._entity_type = ""
        self._entity_id: int | None = None
        self._context: ControlPointContext | None = None
        self._must_be_saved_message = "Záznam je nutné nejdříve uložit."
        self._photo_paths: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 4, 0, 0)
        layout.setSpacing(6)

        header = QLabel(PHOTO_SECTION_LABEL)
        header.setObjectName("InfoText")
        layout.addWidget(header)

        self._thumbnail = _ClickablePhotoLabel()
        self._thumbnail.setObjectName("ControlResultPhotoThumbnail")
        self._thumbnail.setFixedSize(140, 140)
        self._thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail.setText("Bez fotografie")
        self._thumbnail.setScaledContents(False)
        self._thumbnail.clicked.connect(self._view_photo)
        layout.addWidget(self._thumbnail, 0, Qt.AlignmentFlag.AlignLeft)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        self._add_btn = QPushButton(PHOTO_ADD_LABEL)
        self._remove_btn = QPushButton(PHOTO_REMOVE_LABEL)
        self._view_btn = QPushButton(PHOTO_VIEW_LABEL)
        buttons.addWidget(self._add_btn)
        buttons.addWidget(self._remove_btn)
        buttons.addWidget(self._view_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self._add_btn.clicked.connect(self._add_photo)
        self._remove_btn.clicked.connect(self._remove_photo)
        self._view_btn.clicked.connect(self._view_photo)

        self._update_buttons()

    def configure(
        self,
        *,
        entity_type: str,
        entity_id: int | None,
        context: ControlPointContext,
        must_be_saved_message: str,
    ) -> None:
        self._entity_type = entity_type
        self._entity_id = entity_id
        self._context = context
        self._must_be_saved_message = must_be_saved_message
        self.reload()

    def reload(self) -> None:
        self._photo_paths = []
        enabled = self._entity_id is not None and self._context is not None

        if enabled:
            row = control_result_service.get_for_control_point(
                self._entity_type,
                self._entity_id,
                self._context,
            )
            if row and row.photo_path:
                self._photo_paths = [row.photo_path]

        self._refresh_thumbnail()
        self._update_buttons(enabled=enabled)

    def _current_photo_path(self) -> Path | None:
        if not self._photo_paths:
            return None
        absolute = control_result_photo_service.absolute_photo_path(self._photo_paths[0])
        return absolute if absolute.is_file() else None

    def _refresh_thumbnail(self) -> None:
        path = self._current_photo_path()
        if path is None:
            self._thumbnail.setPixmap(QPixmap())
            self._thumbnail.setText("Bez fotografie")
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._thumbnail.setPixmap(QPixmap())
            self._thumbnail.setText("Náhled nedostupný")
            return

        self._thumbnail.setText("")
        self._thumbnail.setPixmap(
            pixmap.scaled(
                self._thumbnail.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _update_buttons(self, *, enabled: bool | None = None) -> None:
        if enabled is None:
            enabled = self._entity_id is not None and self._context is not None

        has_photo = self._current_photo_path() is not None
        self._add_btn.setEnabled(enabled)
        self._remove_btn.setEnabled(enabled and has_photo)
        self._view_btn.setEnabled(has_photo)
        self._thumbnail.setCursor(
            Qt.CursorShape.PointingHandCursor if has_photo else Qt.CursorShape.ArrowCursor
        )

    def _add_photo(self) -> None:
        if self._entity_id is None or self._context is None:
            QMessageBox.information(self, PHOTO_SECTION_LABEL, self._must_be_saved_message)
            return

        selected = PhotoPickerDialog.get_photo(parent=self)
        if selected is None:
            return

        try:
            control_result_service.attach_photo(
                self._entity_type,
                self._entity_id,
                self._context,
                Path(selected),
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                PHOTO_SECTION_LABEL,
                f"Fotografii se nepodařilo uložit.\n\n{exc}",
            )
            return

        self.reload()
        self.photo_changed.emit()

    def _remove_photo(self) -> None:
        if self._entity_id is None or self._context is None:
            return

        answer = QMessageBox.question(
            self,
            PHOTO_SECTION_LABEL,
            "Odebrat fotografii u tohoto kontrolního bodu?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        control_result_service.remove_photo(
            self._entity_type,
            self._entity_id,
            self._context,
        )
        self.reload()
        self.photo_changed.emit()

    def _view_photo(self) -> None:
        path = self._current_photo_path()
        if path is None:
            return

        exec_maximized(ImageViewerDialog(path, title=PHOTO_SECTION_LABEL, parent=self))
