from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.services.storage_service import storage_service
from core.ui.photo_picker_dialog import PhotoPickerDialog
from core.widgets.image_viewer_dialog import ImageViewerDialog
from core.widgets.table_utils import configure_table_columns
from moduly.rizeni_rizik.constants import (
    HAZARD_PHOTO_DIALOG_TITLE,
    HAZARD_PHOTO_MISSING_FILE_MESSAGE,
    PHOTO_COL_ACTIVE,
    PHOTO_COL_CAPTION,
    PHOTO_COL_ID,
    PHOTO_COL_SIZE,
    PHOTO_COL_TAKEN_AT,
    PHOTO_COL_THUMBNAIL,
    PHOTO_COLUMN_COUNT,
    PHOTO_TABLE_HEADERS,
    PHOTOS_INTRO_TEXT,
    format_photo_file_size,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
    find_identification_working_copy,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_photo_service import (
    HazardIdentificationPhotoError,
    hazard_identification_photo_service,
)
from moduly.rizeni_rizik.ui.hazard_identification_photo_dialog import (
    HazardIdentificationPhotoDialog,
)


class HazardIdentificationPhotosWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._identification_id: int | None = None
        self._read_only = False
        self._selected_photo_id: int | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(PHOTOS_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat fotografii")
        self.open_btn = QPushButton("Otevřít")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table = QTableWidget()
        self.table.setColumnCount(PHOTO_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(PHOTO_TABLE_HEADERS)
        self.table.setColumnHidden(PHOTO_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(72)
        configure_table_columns(self.table, "hazard_identification_photos")
        splitter.addWidget(self.table)

        preview_host = QWidget()
        preview_layout = QVBoxLayout(preview_host)
        preview_layout.setContentsMargins(8, 0, 0, 0)
        self.preview_image = QLabel("Vyberte fotografii")
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setMinimumSize(240, 180)
        self.preview_image.setWordWrap(True)
        self.preview_caption = QLabel("")
        self.preview_caption.setWordWrap(True)
        self.preview_note = QLabel("")
        self.preview_note.setWordWrap(True)
        preview_layout.addWidget(self.preview_image, 1)
        preview_layout.addWidget(self.preview_caption)
        preview_layout.addWidget(self.preview_note)
        preview_layout.addStretch()
        splitter.addWidget(preview_host)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, 1)

        self.add_btn.clicked.connect(self.add_photo)
        self.open_btn.clicked.connect(self.open_selected_photo)
        self.edit_btn.clicked.connect(self.edit_selected_photo)
        self.activate_btn.clicked.connect(self.activate_selected_photo)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_photo)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self.open_selected_photo)

        self.set_identification(None, read_only=False)

    def _store(self):
        return find_identification_working_copy(self)

    def _notify_editor_dirty(self) -> None:
        window = self.window()
        update = getattr(window, "_update_save_enabled", None)
        if callable(update):
            update()

    @staticmethod
    def _absolute_photo_path(photo) -> Path:
        staged = getattr(photo, "staged_source_path", None)
        if staged:
            return Path(staged)
        relative = getattr(photo, "relative_path", None)
        if relative:
            return storage_service.attachment_absolute(relative)
        return hazard_identification_photo_service.absolute_path(photo)

    def set_identification(
        self,
        identification_id: int | None,
        *,
        read_only: bool,
    ) -> None:
        self._identification_id = identification_id
        self._read_only = read_only
        self._selected_photo_id = None
        self._update_actions_enabled()
        self.refresh()

    def refresh(self) -> None:
        self._load_table()
        self._update_preview()

    def add_photo(self) -> bool:
        if not self._ensure_editable():
            return False
        paths = PhotoPickerDialog.get_photos(parent=self)
        if not paths:
            return False

        # Jedna fotografie → dialog s metadaty; více → hromadné uložení.
        if len(paths) == 1:
            dialog = HazardIdentificationPhotoDialog(
                self,
                hazard_identification_id=self._identification_id,
                initial_source=paths[0],
            )
            if dialog.exec():
                self.refresh()
                self._notify_editor_dirty()
                return True
            return False

        store = self._store()
        created = 0
        for path in paths:
            if not path.is_file():
                continue
            try:
                if store is not None:
                    store.create_photo(
                        source_path=path,
                        caption=path.stem.strip(),
                        note="",
                        taken_at=None,
                        active=True,
                    )
                else:
                    hazard_identification_photo_service.create_photo(
                        hazard_identification_id=self._identification_id,
                        source_path=path,
                        caption=path.stem.strip(),
                        note="",
                        taken_at=None,
                        active=True,
                    )
                created += 1
            except HazardIdentificationPhotoError as error:
                QMessageBox.warning(self, HAZARD_PHOTO_DIALOG_TITLE, str(error))
                break

        if created:
            self.refresh()
            self._notify_editor_dirty()
            return True
        return False

    def edit_selected_photo(self) -> None:
        photo = self._selected_photo()
        if photo is None:
            QMessageBox.information(self, HAZARD_PHOTO_DIALOG_TITLE, "Vyberte fotografii.")
            return
        dialog = HazardIdentificationPhotoDialog(
            self,
            hazard_identification_id=self._identification_id,
            photo=photo,
            read_only=self._read_only,
        )
        if dialog.exec():
            self.refresh()
            self._notify_editor_dirty()

    def open_selected_photo(self) -> None:
        photo = self._selected_photo()
        if photo is None:
            QMessageBox.information(self, HAZARD_PHOTO_DIALOG_TITLE, "Vyberte fotografii.")
            return
        path = self._absolute_photo_path(photo)
        if not path.is_file():
            QMessageBox.warning(
                self,
                HAZARD_PHOTO_DIALOG_TITLE,
                HAZARD_PHOTO_MISSING_FILE_MESSAGE,
            )
            return
        viewer = ImageViewerDialog(path, title=photo.caption or photo.filename, parent=self)
        viewer.showMaximized()
        viewer.exec()

    def activate_selected_photo(self) -> None:
        if not self._ensure_editable():
            return
        photo = self._selected_photo()
        if photo is None:
            QMessageBox.information(self, HAZARD_PHOTO_DIALOG_TITLE, "Vyberte fotografii.")
            return
        if photo.active:
            QMessageBox.information(self, HAZARD_PHOTO_DIALOG_TITLE, "Fotografie je již aktivní.")
            return
        store = self._store()
        if store is not None:
            store.activate_photo(photo.id)
        else:
            hazard_identification_photo_service.activate_photo(photo.id)
        self.refresh()
        self._notify_editor_dirty()

    def deactivate_selected_photo(self) -> None:
        if not self._ensure_editable():
            return
        photo = self._selected_photo()
        if photo is None:
            QMessageBox.information(self, HAZARD_PHOTO_DIALOG_TITLE, "Vyberte fotografii.")
            return
        if not photo.active:
            QMessageBox.information(
                self,
                HAZARD_PHOTO_DIALOG_TITLE,
                "Fotografie je již neaktivní.",
            )
            return
        store = self._store()
        if store is not None:
            store.deactivate_photo(photo.id)
        else:
            hazard_identification_photo_service.deactivate_photo(photo.id)
        self.refresh()
        self._notify_editor_dirty()

    def _ensure_editable(self) -> bool:
        if self._identification_id is None:
            QMessageBox.information(
                self,
                HAZARD_PHOTO_DIALOG_TITLE,
                "Nejprve uložte základní údaje identifikace.",
            )
            return False
        if self._read_only:
            QMessageBox.information(
                self,
                HAZARD_PHOTO_DIALOG_TITLE,
                "Fotodokumentace je u dokončené nebo archivované identifikace "
                "pouze pro prohlížení.",
            )
            return False
        return True

    def _update_actions_enabled(self) -> None:
        has_source = self._identification_id is not None
        editable = has_source and not self._read_only
        self.add_btn.setEnabled(editable)
        self.edit_btn.setEnabled(editable)
        self.activate_btn.setEnabled(editable)
        self.deactivate_btn.setEnabled(editable)
        self.open_btn.setEnabled(has_source)

    def _load_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if self._identification_id is None:
            self.table.blockSignals(False)
            return

        store = self._store()
        if store is not None:
            rows = store.get_photos(include_inactive=True)
        else:
            rows = hazard_identification_photo_service.get_for_identification(
                self._identification_id,
                include_inactive=True,
            )
        self.table.setRowCount(len(rows))
        selected_row = -1
        for row_index, photo in enumerate(rows):
            self.table.setItem(row_index, PHOTO_COL_ID, QTableWidgetItem(str(photo.id)))

            thumb_item = QTableWidgetItem()
            thumb_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            path = self._absolute_photo_path(photo)
            if path.is_file():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    thumb_item.setData(
                        Qt.ItemDataRole.DecorationRole,
                        pixmap.scaled(
                            96,
                            64,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        ),
                    )
                else:
                    thumb_item.setText("—")
            else:
                thumb_item.setText("chybí")
            self.table.setItem(row_index, PHOTO_COL_THUMBNAIL, thumb_item)

            self.table.setItem(
                row_index,
                PHOTO_COL_CAPTION,
                QTableWidgetItem(photo.caption or "—"),
            )
            taken = (
                photo.taken_at.strftime("%d.%m.%Y")
                if photo.taken_at is not None
                else "—"
            )
            self.table.setItem(row_index, PHOTO_COL_TAKEN_AT, QTableWidgetItem(taken))
            self.table.setItem(
                row_index,
                PHOTO_COL_SIZE,
                QTableWidgetItem(format_photo_file_size(photo.file_size or 0)),
            )
            self.table.setItem(
                row_index,
                PHOTO_COL_ACTIVE,
                QTableWidgetItem("Ano" if photo.active else "Ne"),
            )
            if self._selected_photo_id == photo.id:
                selected_row = row_index

        configure_table_columns(self.table, "hazard_identification_photos")
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self.table.blockSignals(False)

    def _on_selection_changed(self) -> None:
        photo = self._selected_photo()
        self._selected_photo_id = photo.id if photo is not None else None
        self._update_preview()

    def _update_preview(self) -> None:
        photo = self._selected_photo()
        if photo is None:
            self.preview_image.setPixmap(QPixmap())
            self.preview_image.setText("Vyberte fotografii")
            self.preview_caption.setText("")
            self.preview_note.setText("")
            return

        path = self._absolute_photo_path(photo)
        if not path.is_file():
            self.preview_image.setPixmap(QPixmap())
            self.preview_image.setText(HAZARD_PHOTO_MISSING_FILE_MESSAGE)
        else:
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                self.preview_image.setPixmap(QPixmap())
                self.preview_image.setText("Fotografii se nepodařilo načíst.")
            else:
                scaled = pixmap.scaled(
                    360,
                    270,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_image.setPixmap(scaled)
                self.preview_image.setText("")

        self.preview_caption.setText(photo.caption or "(bez popisu)")
        self.preview_note.setText(photo.note or "")

    def _selected_photo(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), PHOTO_COL_ID)
        if id_item is None:
            return None
        photo_id = int(id_item.text())
        store = self._store()
        if store is not None:
            return store.get_photo(photo_id)
        return hazard_identification_photo_service.get_by_id(photo_id)
