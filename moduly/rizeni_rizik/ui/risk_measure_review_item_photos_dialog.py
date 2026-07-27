"""Správce fotografií kontrolního bodu přezkoumání – AttachmentWidget + PhotoPicker."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QVBoxLayout

from core.services.attachment_service import attachment_service
from core.ui.photo_picker_dialog import PhotoPickerDialog
from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.dialog_utils import configure_resizable_form_dialog, create_close_box
from moduly.rizeni_rizik.constants import (
    ENTITY_RISK_MEASURE_REVIEW_ITEM,
    RISK_MEASURE_REVIEW_ITEM_PHOTOS_TITLE,
)


class RiskMeasureReviewItemPhotosDialog(QDialog):
    """Dialog se sdíleným AttachmentWidget; přidání přes PhotoPickerDialog."""

    def __init__(self, parent=None, *, item_id: int):
        super().__init__(parent)
        self.item_id = int(item_id)
        self.setWindowTitle(RISK_MEASURE_REVIEW_ITEM_PHOTOS_TITLE)
        configure_resizable_form_dialog(self, width=560, height=420, min_width=420, min_height=320)

        layout = QVBoxLayout(self)
        self.attachments = AttachmentWidget(
            ENTITY_RISK_MEASURE_REVIEW_ITEM,
            self.item_id,
            parent=self,
        )
        self.attachments.btn_add.setText("Přidat fotografii")
        try:
            self.attachments.btn_add.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.attachments.btn_add.clicked.connect(self._add_photo)
        layout.addWidget(self.attachments)
        buttons = create_close_box(self)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)

    def photo_count(self) -> int:
        return len(
            attachment_service.get_for_entity(
                ENTITY_RISK_MEASURE_REVIEW_ITEM,
                self.item_id,
            )
        )

    def _add_photo(self) -> None:
        selected = PhotoPickerDialog.get_photo(parent=self)
        if selected is None:
            return
        path = Path(selected)
        if not path.is_file():
            QMessageBox.warning(
                self,
                RISK_MEASURE_REVIEW_ITEM_PHOTOS_TITLE,
                "Vybraný soubor fotografie nebyl nalezen.",
            )
            return
        try:
            attachment_service.add_file(
                ENTITY_RISK_MEASURE_REVIEW_ITEM,
                self.item_id,
                str(path),
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                RISK_MEASURE_REVIEW_ITEM_PHOTOS_TITLE,
                f"Fotografii se nepodařilo uložit.\n\n{exc}",
            )
            return
        self.attachments.reload()
