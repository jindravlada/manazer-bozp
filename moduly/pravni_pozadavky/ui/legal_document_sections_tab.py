from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_section_dialog import LegalSectionDialog
from moduly.pravni_pozadavky.ui.legal_section_table import LegalSectionTable


class LegalDocumentSectionsTab(QWidget):
    def __init__(
        self,
        document_id: int | None = None,
        version_id: int | None = None,
    ):
        super().__init__()
        self.document_id = document_id
        self.version_id = version_id

        layout = QVBoxLayout(self)

        if version_id is None:
            layout.addWidget(QLabel("Strukturu lze přidat až po uložení verze předpisu."))
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

        self.table = LegalSectionTable()

        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self.add_section)
        self.edit_btn.clicked.connect(self.edit_selected_section)
        self.toggle_btn.clicked.connect(self.toggle_selected_section)
        self.table.doubleClicked.connect(self.edit_selected_section)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def refresh(self) -> None:
        if self.table is None or self.version_id is None:
            return
        sections = legal_section_service.list_by_version(
            self.version_id,
            include_inactive=True,
        )
        self.table.load_sections(sections)
        self._update_action_buttons()

    def _selected_section(self):
        if self.table is None:
            return None
        section_id = self.table.selected_section_id()
        if section_id is None:
            return None
        return legal_section_service.get_by_id(section_id)

    def _update_action_buttons(self) -> None:
        if self.toggle_btn is None:
            return
        section = self._selected_section()
        if section is None:
            self.toggle_btn.setText("Deaktivovat")
            return
        self.toggle_btn.setText("Obnovit" if not section.active else "Deaktivovat")

    def add_section(self) -> None:
        if self.document_id is None or self.version_id is None:
            return

        dialog = LegalSectionDialog(self)
        if not exec_maximized(dialog):
            return

        try:
            legal_section_service.create(
                legal_document_id=self.document_id,
                legal_document_version_id=self.version_id,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Část předpisu", str(exc))
            return
        self.refresh()

    def edit_selected_section(self) -> None:
        section = self._selected_section()
        if section is None:
            QMessageBox.information(self, "Část předpisu", "Vyberte část předpisu.")
            return

        dialog = LegalSectionDialog(self, section=section)
        if not exec_maximized(dialog):
            return

        try:
            legal_section_service.update(
                section.id,
                legal_document_id=self.document_id,
                legal_document_version_id=self.version_id,
                active=section.active,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Část předpisu", str(exc))
            return
        self.refresh()

    def toggle_selected_section(self) -> None:
        section = self._selected_section()
        if section is None:
            QMessageBox.information(self, "Část předpisu", "Vyberte část předpisu.")
            return

        if section.active:
            answer = QMessageBox.question(
                self,
                "Deaktivovat část",
                "Opravdu deaktivovat vybranou část předpisu?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                legal_section_service.deactivate(section.id)
                self.refresh()
            return

        legal_section_service.restore(section.id)
        self.refresh()
