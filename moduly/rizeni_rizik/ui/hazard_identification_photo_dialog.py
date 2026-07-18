from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.rizeni_rizik.constants import HAZARD_PHOTO_DIALOG_TITLE
from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
    find_identification_working_copy,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_photo_service import (
    HazardIdentificationPhotoError,
    hazard_identification_photo_service,
)


class HazardIdentificationPhotoDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        hazard_identification_id: int,
        photo=None,
        read_only: bool = False,
    ):
        super().__init__(parent)

        self.hazard_identification_id = hazard_identification_id
        self.photo = photo
        self.read_only = read_only
        self._source_path: Path | None = None

        self.setWindowTitle(HAZARD_PHOTO_DIALOG_TITLE)
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        file_row = QHBoxLayout()
        self.file_label = QLabel("—")
        self.file_label.setWordWrap(True)
        self.browse_btn = QPushButton("Vybrat…")
        self.browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(self.browse_btn)
        form.addRow("Soubor *:", file_row)

        self.caption = QLineEdit()
        self.taken_at = NullableDateEdit()
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(80)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Popis:", self.caption)
        form.addRow("Datum pořízení:", self.taken_at)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if photo is not None:
            self.file_label.setText(photo.filename or photo.stored_filename or "—")
            self.caption.setText(photo.caption or "")
            if photo.taken_at is not None:
                self.taken_at.set_date_value(photo.taken_at.date())
            self.note.setPlainText(photo.note or "")
            self.active_checkbox.setChecked(bool(photo.active))
            self.browse_btn.setEnabled(False)
            self.browse_btn.setVisible(False)
        else:
            self.browse_btn.setEnabled(True)

        if read_only:
            self.browse_btn.setEnabled(False)
            self.caption.setReadOnly(True)
            self.taken_at.setEnabled(False)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vybrat fotografii",
            "",
            "Fotografie (*.jpg *.jpeg *.png *.webp);;Všechny soubory (*)",
        )
        if not path:
            return
        source = Path(path)
        self._source_path = source
        self.file_label.setText(source.name)
        if self.taken_at.get_date() is None:
            peeked = hazard_identification_photo_service.peek_taken_at(source)
            if peeked is not None:
                self.taken_at.set_date_value(peeked.date())

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        try:
            store = find_identification_working_copy(self)
            if store is not None:
                if self.photo is None:
                    if self._source_path is None:
                        QMessageBox.warning(
                            self,
                            HAZARD_PHOTO_DIALOG_TITLE,
                            "Vyberte soubor fotografie.",
                        )
                        return
                    store.create_photo(
                        source_path=self._source_path,
                        caption=self.caption.text().strip(),
                        note=self.note.toPlainText().strip(),
                        taken_at=self.taken_at.get_date(),
                        active=self.active_checkbox.isChecked(),
                    )
                else:
                    store.update_photo(
                        self.photo.id,
                        caption=self.caption.text().strip(),
                        note=self.note.toPlainText().strip(),
                        taken_at=self.taken_at.get_date(),
                        active=self.active_checkbox.isChecked(),
                    )
            elif self.photo is None:
                if self._source_path is None:
                    QMessageBox.warning(
                        self,
                        HAZARD_PHOTO_DIALOG_TITLE,
                        "Vyberte soubor fotografie.",
                    )
                    return
                hazard_identification_photo_service.create_photo(
                    hazard_identification_id=self.hazard_identification_id,
                    source_path=self._source_path,
                    caption=self.caption.text().strip(),
                    note=self.note.toPlainText().strip(),
                    taken_at=self.taken_at.get_date(),
                    active=self.active_checkbox.isChecked(),
                )
            else:
                hazard_identification_photo_service.update_photo(
                    self.photo.id,
                    hazard_identification_id=self.hazard_identification_id,
                    caption=self.caption.text().strip(),
                    note=self.note.toPlainText().strip(),
                    taken_at=self.taken_at.get_date(),
                    active=self.active_checkbox.isChecked(),
                )
        except HazardIdentificationPhotoError as error:
            QMessageBox.warning(self, HAZARD_PHOTO_DIALOG_TITLE, str(error))
            return
        super().accept()
