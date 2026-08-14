"""Odložené přílohy externího auditu — zápis až při hlavním Uložit."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.export.open_export import open_local_file
from core.services.attachment_service import attachment_service
from moduly.externi_audity.constants import (
    ENTITY_EXTERNAL_AUDIT,
    EXTERNAL_AUDIT_ATTACHMENTS_NEED_SAVE,
)
from moduly.externi_audity.sluzby.external_audit_draft import AttachmentStagingState


class ExternalAuditAttachmentStagingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._audit_id: int | None = None
        self._staging = AttachmentStagingState()
        self._existing: list = []

        layout = QVBoxLayout(self)
        self.hint = QLabel(EXTERNAL_AUDIT_ATTACHMENTS_NEED_SAVE)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        buttons = QHBoxLayout()
        self.btn_add = QPushButton("Přidat přílohy")
        self.btn_open = QPushButton("Otevřít")
        self.btn_remove = QPushButton("Odebrat")
        buttons.addWidget(self.btn_add)
        buttons.addWidget(self.btn_open)
        buttons.addWidget(self.btn_remove)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.list = QListWidget()
        layout.addWidget(self.list, 1)

        self.btn_add.clicked.connect(self.add_files)
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_remove.clicked.connect(self.remove_selected)

        self.set_audit_id(None)

    @property
    def staging(self) -> AttachmentStagingState:
        return self._staging

    def set_audit_id(self, audit_id: int | None) -> None:
        self._audit_id = int(audit_id) if audit_id else None
        enabled = self._audit_id is not None
        self.hint.setVisible(not enabled)
        self.btn_add.setEnabled(enabled)
        self.btn_open.setEnabled(enabled)
        self.btn_remove.setEnabled(enabled)
        self.list.setEnabled(enabled)
        if not enabled:
            self._existing = []
            self._staging.clear()
            self.list.clear()
            return
        self.reload_existing()

    def reload_existing(self) -> None:
        self._existing = []
        if self._audit_id is None:
            return
        self._existing = attachment_service.get_for_entity(
            ENTITY_EXTERNAL_AUDIT, self._audit_id
        )
        self._refresh_list()

    def reset_staging(self) -> None:
        self._staging.clear()
        self._refresh_list()

    def has_changes(self) -> bool:
        return self._staging.has_changes()

    def add_files(self) -> None:
        if self._audit_id is None:
            QMessageBox.information(
                self, "Přílohy", EXTERNAL_AUDIT_ATTACHMENTS_NEED_SAVE
            )
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Vyberte přílohy",
            "",
            "PDF a dokumenty (*.pdf *.odt *.docx *.xlsx *.png *.jpg *.jpeg);;Všechny soubory (*.*)",
        )
        for path in files:
            if path and path not in self._staging.pending_add_paths:
                self._staging.pending_add_paths.append(path)
        self._refresh_list()

    def remove_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        kind = item.data(Qt.ItemDataRole.UserRole)
        payload = item.data(Qt.ItemDataRole.UserRole + 1)
        if kind == "pending":
            path = str(payload)
            self._staging.pending_add_paths = [
                value
                for value in self._staging.pending_add_paths
                if value != path
            ]
        elif kind == "existing":
            attachment_id = int(payload)
            if attachment_id not in self._staging.pending_remove_ids:
                self._staging.pending_remove_ids.append(attachment_id)
        self._refresh_list()

    def open_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        kind = item.data(Qt.ItemDataRole.UserRole)
        payload = item.data(Qt.ItemDataRole.UserRole + 1)
        if kind == "pending":
            open_local_file(str(payload))
            return
        if kind == "existing":
            attachment_id = int(payload)
            for attachment in self._existing:
                if int(attachment.id) == attachment_id:
                    path = attachment_service.resolve_path(attachment)
                    open_local_file(str(path))
                    return

    def _refresh_list(self) -> None:
        self.list.clear()
        remove_ids = set(self._staging.pending_remove_ids)
        for attachment in self._existing:
            if int(attachment.id) in remove_ids:
                continue
            size = self._file_size_label(attachment)
            suffix = Path(attachment.filename or "").suffix.lstrip(".").upper() or "?"
            text = f"{attachment.filename or 'příloha'}  ({suffix}, {size})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, "existing")
            item.setData(Qt.ItemDataRole.UserRole + 1, int(attachment.id))
            self.list.addItem(item)
        for path in self._staging.pending_add_paths:
            name = Path(path).name
            suffix = Path(path).suffix.lstrip(".").upper() or "?"
            size = self._path_size_label(path)
            item = QListWidgetItem(f"{name}  ({suffix}, {size}) — nové")
            item.setData(Qt.ItemDataRole.UserRole, "pending")
            item.setData(Qt.ItemDataRole.UserRole + 1, path)
            self.list.addItem(item)

    def _file_size_label(self, attachment) -> str:
        try:
            path = attachment_service.resolve_path(attachment)
            return self._path_size_label(str(path))
        except Exception:
            return "?"

    @staticmethod
    def _path_size_label(path: str) -> str:
        try:
            size = Path(path).stat().st_size
        except OSError:
            return "?"
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"
