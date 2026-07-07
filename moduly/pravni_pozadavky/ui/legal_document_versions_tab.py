from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.ui.legal_document_version_dialog import LegalDocumentVersionDialog
from moduly.pravni_pozadavky.ui.legal_document_version_table import LegalDocumentVersionTable


class LegalDocumentVersionsTab(QWidget):
    def __init__(self, document_id: int | None = None):
        super().__init__()
        self.document_id = document_id

        layout = QVBoxLayout(self)

        if document_id is None:
            layout.addWidget(QLabel("Verze lze přidat až po uložení právního předpisu."))
            self.table = None
            self.add_btn = None
            self.edit_btn = None
            self.toggle_btn = None
            return

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.toggle_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.toggle_btn)
        toolbar.addStretch()

        self.table = LegalDocumentVersionTable()

        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self.add_version)
        self.edit_btn.clicked.connect(self.edit_selected_version)
        self.toggle_btn.clicked.connect(self.toggle_selected_version)
        self.table.doubleClicked.connect(self.edit_selected_version)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def refresh(self) -> None:
        if self.table is None or self.document_id is None:
            return
        versions = legal_document_version_service.list_by_document(
            self.document_id,
            include_inactive=True,
        )
        self.table.load_versions(versions)
        self._update_action_buttons()

    def _selected_version(self):
        if self.table is None:
            return None
        version_id = self.table.selected_version_id()
        if version_id is None:
            return None
        return legal_document_version_service.get_by_id(version_id)

    def _update_action_buttons(self) -> None:
        if self.toggle_btn is None:
            return
        version = self._selected_version()
        if version is None:
            self.toggle_btn.setText("Deaktivovat")
            return
        self.toggle_btn.setText("Obnovit" if not version.active else "Deaktivovat")

    def add_version(self) -> None:
        if self.document_id is None:
            return

        dialog = LegalDocumentVersionDialog(self, document_id=self.document_id)
        if not exec_maximized(dialog):
            return

        try:
            legal_document_version_service.create(
                legal_document_id=self.document_id,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Verze předpisu", str(exc))
            return
        self.refresh()

    def edit_selected_version(self) -> None:
        version = self._selected_version()
        if version is None:
            QMessageBox.information(self, "Verze předpisu", "Vyberte verzi.")
            return

        dialog = LegalDocumentVersionDialog(self, version=version)
        if not exec_maximized(dialog):
            return

        try:
            legal_document_version_service.update(
                version.id,
                legal_document_id=self.document_id,
                active=version.active,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Verze předpisu", str(exc))
            return
        self.refresh()

    def toggle_selected_version(self) -> None:
        version = self._selected_version()
        if version is None:
            QMessageBox.information(self, "Verze předpisu", "Vyberte verzi.")
            return

        if version.active:
            answer = QMessageBox.question(
                self,
                "Deaktivovat verzi",
                "Opravdu deaktivovat vybranou verzi?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                legal_document_version_service.deactivate(version.id)
                self.refresh()
            return

        legal_document_version_service.restore(version.id)
        self.refresh()
