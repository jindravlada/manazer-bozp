from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from moduly.pravni_pozadavky.constants import legal_section_display_label
from moduly.pravni_pozadavky.sluzby.legal_requirement_creation_service import (
    legal_requirement_creation_service,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_requirement_workbench_editor import (
    LegalRequirementWorkbenchEditor,
)
from moduly.pravni_pozadavky.ui.legal_section_tree import (
    LegalSectionTree,
    next_processable_section,
)


def _find_pravni_pozadavky_page(widget):
    from moduly.pravni_pozadavky.ui.pravni_pozadavky_page import PravniPozadavkyPage

    current = widget
    while current is not None:
        if isinstance(current, PravniPozadavkyPage):
            return current
        current = current.parentWidget()
    return None


class LegalDocumentWorkbenchTab(QWidget):
    def __init__(
        self,
        document_id: int | None = None,
        version_id: int | None = None,
    ):
        super().__init__()
        self.document_id = document_id
        self.version_id = version_id
        self._sections = []
        self._suppress_selection_load = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if version_id is None:
            layout.addWidget(
                QLabel("Pracovní režim bude dostupný až po uložení verze předpisu."),
            )
            self.tree = None
            self.editor = None
            return

        splitter = QSplitter()
        self.tree = LegalSectionTree()
        self.editor = LegalRequirementWorkbenchEditor()

        splitter.addWidget(self.tree)
        splitter.addWidget(self.editor)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.tree.itemSelectionChanged.connect(self._on_section_selected)
        self.editor.save_btn.clicked.connect(self.save_current)
        self.editor.next_btn.clicked.connect(self.save_and_next)

        self.refresh()

    def refresh(self) -> None:
        if self.tree is None or self.version_id is None:
            return
        self._sections = legal_section_service.list_by_version(
            self.version_id,
            include_inactive=True,
        )
        section_ids = [section.id for section in self._sections]
        section_statuses = legal_requirement_service.get_source_section_requirement_statuses(
            section_ids,
        )
        self.tree.load_sections(
            self._sections,
            section_requirement_statuses=section_statuses,
        )

    def _on_section_selected(self) -> None:
        if self._suppress_selection_load or self.tree is None or self.editor is None:
            return
        section_id = self.tree.selected_section_id()
        if section_id is None:
            self.editor.clear_form()
            return
        self.load_section(section_id)

    def load_section(self, section_id: int) -> None:
        if self.editor is None:
            return

        section = legal_section_service.get_by_id(section_id)
        if section is None:
            self.editor.clear_form()
            return

        if not LegalSectionTree.allows_requirement_creation(section.section_type):
            self.editor.clear_form()
            return

        context_label = legal_section_display_label(section)
        section_text = section.text or ""
        existing = legal_requirement_service.get_by_source_section_id(section_id)
        if existing is not None:
            self.editor.load_requirement(
                existing,
                section_text=section_text,
                context_label=context_label,
            )
            return

        try:
            draft = legal_requirement_creation_service.create_from_section(section_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Právní požadavek", str(exc))
            self.editor.clear_form()
            return

        self.editor.load_draft(
            draft,
            section_text=section_text,
            context_label=context_label,
        )

    def save_current(self) -> int | None:
        if self.editor is None:
            return None

        section_id = self.editor.current_section_id()
        if section_id is None:
            QMessageBox.information(self, "Právní požadavek", "Vyberte ustanovení předpisu.")
            return None

        data = self.editor.get_data()
        try:
            requirement_id = self._persist_requirement(data)
        except ValueError as exc:
            QMessageBox.warning(self, "Právní požadavek", str(exc))
            return None

        self.refresh()
        self._reselect_section(section_id)
        self.load_section(section_id)
        self._notify_requirements_page(requirement_id)
        return requirement_id

    def save_and_next(self) -> int | None:
        current_section_id = self.editor.current_section_id() if self.editor is not None else None
        requirement_id = self.save_current()
        if requirement_id is None or current_section_id is None or self.tree is None:
            return requirement_id

        next_section = next_processable_section(self._sections, current_section_id)
        if next_section is None:
            QMessageBox.information(
                self,
                "Právní požadavek",
                "Aktuální ustanovení je poslední vhodné pro zpracování.",
            )
            return requirement_id

        self._reselect_section(next_section.id)
        self.load_section(next_section.id)
        return requirement_id

    def _persist_requirement(self, data: dict) -> int:
        source_section_id = data.get("source_section_id")
        existing = None
        if source_section_id is not None:
            existing = legal_requirement_service.get_by_source_section_id(source_section_id)

        if existing is not None:
            updated = legal_requirement_service.update_requirement(existing.id, **data)
            if updated is None:
                raise ValueError("Požadavek nebyl nalezen.")
            return updated.id

        created = legal_requirement_service.create_requirement(**data)
        if created.id is None:
            raise ValueError("Požadavek se nepodařilo uložit.")
        return created.id

    def _reselect_section(self, section_id: int) -> None:
        if self.tree is None:
            return
        self._suppress_selection_load = True
        try:
            self.tree.select_section_id(section_id)
        finally:
            self._suppress_selection_load = False

    def _notify_requirements_page(self, requirement_id: int) -> None:
        page = _find_pravni_pozadavky_page(self)
        if page is not None:
            page.on_requirement_created(requirement_id)
