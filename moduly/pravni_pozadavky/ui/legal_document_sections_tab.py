from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from moduly.pravni_pozadavky.sluzby.legal_requirement_creation_service import (
    legal_requirement_creation_service,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_requirement_dialog import LegalRequirementDialog
from moduly.pravni_pozadavky.ui.legal_section_dialog import LegalSectionDialog
from moduly.pravni_pozadavky.ui.legal_section_tree import LegalSectionTree, load_version_sections_into_tree


def _find_pravni_pozadavky_page(widget):
    from moduly.pravni_pozadavky.ui.pravni_pozadavky_page import PravniPozadavkyPage

    current = widget
    while current is not None:
        if isinstance(current, PravniPozadavkyPage):
            return current
        current = current.parentWidget()
    return None


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
            self.tree = None
            self.add_btn = None
            self.edit_btn = None
            self.toggle_btn = None
            self.create_requirement_btn = None
            return

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.create_requirement_btn = QPushButton("Vytvořit právní požadavek")
        self.edit_btn = QPushButton("Upravit")
        self.toggle_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.create_requirement_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.toggle_btn)
        toolbar.addStretch()

        self.tree = LegalSectionTree()

        layout.addLayout(toolbar)
        layout.addWidget(self.tree)

        self.add_btn.clicked.connect(self.add_section)
        self.create_requirement_btn.clicked.connect(self.create_requirement_from_section)
        self.edit_btn.clicked.connect(self.edit_selected_section)
        self.toggle_btn.clicked.connect(self.toggle_selected_section)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def refresh(self) -> None:
        if self.tree is None or self.version_id is None:
            return
        sections = legal_section_service.list_by_version(
            self.version_id,
            include_inactive=True,
        )
        load_version_sections_into_tree(self.tree, sections)
        self._update_action_buttons()

    def _selected_section(self):
        if self.tree is None:
            return None
        section_id = self.tree.selected_section_id()
        if section_id is None:
            return None
        return legal_section_service.get_by_id(section_id)

    def _update_action_buttons(self) -> None:
        if self.toggle_btn is None or self.create_requirement_btn is None:
            return
        section = self._selected_section()
        section_type = self.tree.selected_section_type() if self.tree is not None else None
        self.create_requirement_btn.setEnabled(
            LegalSectionTree.allows_requirement_creation(section_type),
        )
        if section is None:
            self.toggle_btn.setText("Deaktivovat")
            return
        self.toggle_btn.setText("Obnovit" if not section.active else "Deaktivovat")

    def _on_item_double_clicked(self, _item, _column: int) -> None:
        self.edit_selected_section()

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

    def create_requirement_from_section(self) -> None:
        section = self._selected_section()
        if section is None:
            QMessageBox.information(self, "Právní požadavek", "Vyberte ustanovení předpisu.")
            return

        if not LegalSectionTree.allows_requirement_creation(section.section_type):
            QMessageBox.information(
                self,
                "Právní požadavek",
                "Právní požadavek lze vytvořit pouze z paragrafu, odstavce nebo písmene.",
            )
            return

        try:
            draft = legal_requirement_creation_service.create_from_section(section.id)
        except ValueError as exc:
            QMessageBox.warning(self, "Právní požadavek", str(exc))
            return

        dialog = LegalRequirementDialog(self, draft=draft)
        if not exec_maximized(dialog):
            return

        try:
            requirement = legal_requirement_service.create_requirement(**dialog.get_data())
        except ValueError as exc:
            QMessageBox.warning(self, "Právní požadavek", str(exc))
            return
        self.refresh()
        self._notify_requirements_page(requirement.id)

    def _notify_requirements_page(self, requirement_id: int) -> None:
        page = _find_pravni_pozadavky_page(self)
        if page is not None:
            page.on_requirement_created(requirement_id)

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
