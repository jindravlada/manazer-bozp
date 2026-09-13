from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.export.open_export import open_local_file
from core.services.attachment_service import attachment_service
from core.services.photo_optimization import PhotoOptimizationError


class AttachmentWidget(QWidget):
    """
    Globální komponenta pro přílohy.
    Ukládá soubory přes AttachmentService do:
    ~/.local/share/manazer-bozp/prilohy/
    """

    def __init__(self, entity_type: str = "", entity_id: int | None = None, parent=None):
        super().__init__(parent)

        self.entity_type = entity_type
        self.entity_id = entity_id
        self._attachments = []

        layout = QVBoxLayout(self)

        self.list = QListWidget()

        buttons = QHBoxLayout()

        self.btn_add = QPushButton("Přidat přílohu")
        self.btn_open = QPushButton("Otevřít")
        self.btn_remove = QPushButton("Odebrat")

        buttons.addWidget(self.btn_add)
        buttons.addWidget(self.btn_open)
        buttons.addWidget(self.btn_remove)
        buttons.addStretch()

        layout.addLayout(buttons)
        layout.addWidget(self.list)

        self.btn_add.clicked.connect(self.add_attachment)
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.list.doubleClicked.connect(self.open_selected)

        self.reload()

    def set_entity(self, entity_type: str, entity_id: int | None):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.reload()

    def reload(self):
        self.list.clear()
        self._attachments = []

        enabled = bool(self.entity_type and self.entity_id)
        self.btn_add.setEnabled(enabled)
        self.btn_open.setEnabled(enabled)
        self.btn_remove.setEnabled(enabled)

        if not enabled:
            return

        self._attachments = attachment_service.get_for_entity(self.entity_type, self.entity_id)

        for attachment in self._attachments:
            self.list.addItem(attachment.filename or Path(attachment.stored_path).name)

    def add_attachment(self):
        if not self.entity_type or not self.entity_id:
            QMessageBox.information(
                self,
                "Přílohy",
                "Přílohy lze přidat až po uložení záznamu.",
            )
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Vyberte přílohy",
            "",
            "Všechny soubory (*.*)",
        )

        for file in files:
            try:
                attachment_service.add_file(self.entity_type, self.entity_id, file)
            except PhotoOptimizationError as exc:
                QMessageBox.warning(self, "Přílohy", str(exc))

        self.reload()

    def _selected_attachment(self):
        row = self.list.currentRow()
        if row < 0 or row >= len(self._attachments):
            return None
        return self._attachments[row]

    def open_selected(self):
        attachment = self._selected_attachment()
        if attachment is None:
            return

        try:
            path = attachment_service.resolve_path(attachment)
        except ValueError:
            QMessageBox.warning(self, "Přílohy", "Soubor nebyl nalezen.")
            return

        if not path.exists():
            QMessageBox.warning(self, "Přílohy", "Soubor nebyl nalezen.")
            return

        open_local_file(path, parent=self, title="Přílohy")

    def remove_selected(self):
        attachment = self._selected_attachment()
        if attachment is None:
            return

        answer = QMessageBox.question(
            self,
            "Odebrat přílohu",
            "Opravdu odebrat vybranou přílohu ze záznamu?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.Yes:
            attachment_service.delete(attachment.id)
            self.reload()
