"""Odložené přílohy spisu státního dozoru — zápis až při hlavním Uložit."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.export.open_export import open_local_file
from core.models.attachment_staging import AttachmentStagingState
from core.services.attachment_service import attachment_service
from core.widgets.dialog_utils import configure_new_action_button
from core.widgets.table_utils import apply_cell_tooltip, configure_table_columns
from moduly.statni_dozor.constants import (
    ACTION_ADD_ATTACHMENTS,
    ACTION_OPEN,
    ACTION_REMOVE,
    ACTION_RESTORE,
    ATTACHMENT_COLUMN_HEADERS,
    ATTACHMENT_DUPLICATE_MANY,
    ATTACHMENT_DUPLICATE_ONE,
    ATTACHMENT_FILE_FILTER,
    ATTACHMENT_FILE_MISSING,
    ATTACHMENT_OPEN_ERROR,
    ATTACHMENT_OPEN_TITLE,
    ATTACHMENT_STATUS_NEW,
    ATTACHMENT_STATUS_REMOVE,
    ATTACHMENT_STATUS_SAVED,
    ATTACHMENTS_HINT,
    COL_ATTACHMENT_NAME,
    COL_ATTACHMENT_SIZE,
    COL_ATTACHMENT_STATUS,
    COL_ATTACHMENT_TYPE,
    EMPTY_ATTACHMENTS,
    EMPTY_VALUE,
    GROUP_ATTACHMENTS,
)

logger = logging.getLogger(__name__)

_ROLE_KIND = Qt.ItemDataRole.UserRole
_ROLE_PAYLOAD = Qt.ItemDataRole.UserRole + 1
_KIND_EXISTING = "existing"
_KIND_PENDING = "pending"


class StateSupervisionAttachmentStagingWidget(QWidget):
    """Pracovní seznam příloh. Nic nekopíruje a nic nezapisuje do DB."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        staging: AttachmentStagingState,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._staging = staging
        self._existing: list = []
        self._on_changed = on_changed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.hint = QLabel(ATTACHMENTS_HINT)
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #666;")
        layout.addWidget(self.hint)

        toolbar = QHBoxLayout()
        self.btn_add = QPushButton(ACTION_ADD_ATTACHMENTS)
        self.btn_open = QPushButton(ACTION_OPEN)
        self.btn_remove = QPushButton(ACTION_REMOVE)
        configure_new_action_button(self.btn_add)
        for button in (self.btn_add, self.btn_open, self.btn_remove):
            button.setAutoDefault(False)
            button.setDefault(False)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.empty_label = QLabel(EMPTY_ATTACHMENTS)
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("color: #666;")
        layout.addWidget(self.empty_label)

        self.table = QTableWidget(0, len(ATTACHMENT_COLUMN_HEADERS))
        self.table.setHorizontalHeaderLabels(ATTACHMENT_COLUMN_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setMinimumHeight(140)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        configure_table_columns(self.table, "state_supervision_attachments")
        layout.addWidget(self.table, 1)

        self.btn_add.clicked.connect(self.add_files)
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_remove.clicked.connect(self.remove_or_restore_selected)
        self.table.doubleClicked.connect(self.open_selected)
        self.table.itemSelectionChanged.connect(self._refresh_actions)
        self._refresh_actions()
        self.refresh()

    @property
    def staging(self) -> AttachmentStagingState:
        return self._staging

    def bind_staging(self, staging: AttachmentStagingState) -> None:
        self._staging = staging
        self.refresh()

    def set_existing(self, rows: Sequence) -> None:
        self._existing = list(rows)
        self.refresh()

    def refresh(self) -> None:
        selected = self._current_selection()
        self.table.setRowCount(0)
        rows: list[tuple[str, object, str, str, str, str, bool]] = []
        for attachment in self._existing:
            ident = int(attachment.id)
            name = str(
                attachment.filename
                or Path(str(attachment.stored_path or "")).name
                or "příloha"
            )
            path = self._existing_path(attachment)
            status = (
                ATTACHMENT_STATUS_REMOVE
                if self._staging.is_marked_for_removal(ident)
                else ATTACHMENT_STATUS_SAVED
            )
            size, missing = self._size_label(path)
            rows.append((_KIND_EXISTING, ident, name, path, status, size, missing))
        for source in self._staging.pending_add_paths:
            name = Path(source).name or "příloha"
            size, missing = self._size_label(source)
            rows.append(
                (
                    _KIND_PENDING,
                    source,
                    name,
                    str(source),
                    ATTACHMENT_STATUS_NEW,
                    size,
                    missing,
                )
            )

        empty = not rows
        self.empty_label.setVisible(empty)
        self.table.setVisible(not empty)
        for kind, payload, name, path, status, size, missing in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = self._cell(name)
            name_item.setData(_ROLE_KIND, kind)
            name_item.setData(_ROLE_PAYLOAD, payload)
            tooltip = name if not path else f"{name}\n{path}"
            if missing:
                tooltip = f"{tooltip}\n{ATTACHMENT_FILE_MISSING}"
            apply_cell_tooltip(name_item, tooltip)
            self.table.setItem(row, COL_ATTACHMENT_NAME, name_item)
            self.table.setItem(row, COL_ATTACHMENT_TYPE, self._cell(self._type_label(name)))
            self.table.setItem(row, COL_ATTACHMENT_SIZE, self._cell(size))
            self.table.setItem(row, COL_ATTACHMENT_STATUS, self._cell(status))

        self._restore_selection(selected)
        self._refresh_actions()

    def add_files(self, *_args) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            ACTION_ADD_ATTACHMENTS,
            "",
            ATTACHMENT_FILE_FILTER,
        )
        self.add_paths(files)

    def add_paths(self, paths: Sequence[str]) -> int:
        skipped = 0
        added = 0
        for path in paths:
            text = str(path or "").strip()
            if not text:
                continue
            if self._staging.add_pending_path(text):
                added += 1
            else:
                skipped += 1
        if added:
            self.refresh()
            self._notify_changed()
        if skipped == 1:
            QMessageBox.information(self, GROUP_ATTACHMENTS, ATTACHMENT_DUPLICATE_ONE)
        elif skipped > 1:
            QMessageBox.information(
                self,
                GROUP_ATTACHMENTS,
                ATTACHMENT_DUPLICATE_MANY.format(count=skipped),
            )
        return skipped

    def open_selected(self, *_args) -> None:
        selection = self._current_selection()
        if selection is None:
            return
        kind, payload = selection
        path: Path | None = None
        try:
            if kind == _KIND_PENDING:
                path = Path(str(payload))
            else:
                attachment = self._existing_by_id(int(payload))
                if attachment is None:
                    raise FileNotFoundError(str(payload))
                path = attachment_service.resolve_path(attachment)
            if path is None:
                raise FileNotFoundError("příloha")
            opened = open_local_file(path, parent=self, title=ATTACHMENT_OPEN_TITLE)
            if not opened:
                logger.warning("Soubor přílohy se nepodařilo otevřít: %s", path)
        except Exception:
            logger.exception("Otevření přílohy spisu selhalo.")
            QMessageBox.warning(self, ATTACHMENT_OPEN_TITLE, ATTACHMENT_OPEN_ERROR)

    def remove_or_restore_selected(self, *_args) -> None:
        selection = self._current_selection()
        if selection is None:
            return
        kind, payload = selection
        changed = False
        if kind == _KIND_PENDING:
            changed = self._staging.remove_pending_path(str(payload))
        elif self._staging.is_marked_for_removal(int(payload)):
            changed = self._staging.unmark_for_removal(int(payload))
        else:
            changed = self._staging.mark_for_removal(int(payload))
        if changed:
            self.refresh()
            self._notify_changed()

    def _notify_changed(self) -> None:
        if self._on_changed is not None:
            self._on_changed()

    def _refresh_actions(self) -> None:
        selection = self._current_selection()
        has_row = selection is not None
        self.btn_open.setEnabled(has_row)
        self.btn_remove.setEnabled(has_row)
        if (
            has_row
            and selection[0] == _KIND_EXISTING
            and self._staging.is_marked_for_removal(int(selection[1]))
        ):
            self.btn_remove.setText(ACTION_RESTORE)
        else:
            self.btn_remove.setText(ACTION_REMOVE)

    def _current_selection(self) -> tuple[str, object] | None:
        model = self.table.selectionModel()
        if model is None or not model.selectedRows():
            return None
        row = model.selectedRows()[0].row()
        item = self.table.item(row, COL_ATTACHMENT_NAME)
        if item is None:
            return None
        kind = item.data(_ROLE_KIND)
        payload = item.data(_ROLE_PAYLOAD)
        if not kind:
            return None
        return str(kind), payload

    def _restore_selection(self, selected: tuple[str, object] | None) -> None:
        if selected is None:
            self.table.clearSelection()
            self.table.setCurrentItem(None)
            return
        kind, payload = selected
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_ATTACHMENT_NAME)
            if item is None:
                continue
            if item.data(_ROLE_KIND) == kind and item.data(_ROLE_PAYLOAD) == payload:
                self.table.selectRow(row)
                return

    def _existing_by_id(self, attachment_id: int):
        for attachment in self._existing:
            if int(attachment.id) == attachment_id:
                return attachment
        return None

    @staticmethod
    def _existing_path(attachment) -> str:
        try:
            return str(attachment_service.resolve_path(attachment))
        except Exception:
            return str(attachment.stored_path or "")

    @staticmethod
    def _type_label(name: str) -> str:
        suffix = Path(name).suffix.lstrip(".").upper()
        return suffix or EMPTY_VALUE

    @staticmethod
    def _size_label(path: str) -> tuple[str, bool]:
        if not path:
            return ATTACHMENT_FILE_MISSING, True
        try:
            size = Path(path).stat().st_size
        except OSError:
            return ATTACHMENT_FILE_MISSING, True
        if size < 1024:
            return f"{size} B", False
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} kB", False
        return f"{size / (1024 * 1024):.1f} MB", False

    @staticmethod
    def _cell(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item
