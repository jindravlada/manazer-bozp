from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from moduly.pravni_pozadavky.constants import (
    legal_document_list_label,
    legal_section_provision_label,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_section_tree import (
    LegalSectionTree,
    build_section_children_map,
)

_SECTION_ID_ROLE = Qt.ItemDataRole.UserRole
_ALREADY_ASSIGNED_ROLE = Qt.ItemDataRole.UserRole + 1


class LegalRequirementSourceAddDialog(QDialog):
    def __init__(self, parent=None, *, excluded_section_ids: set[int] | None = None):
        super().__init__(parent)
        self._excluded_section_ids = excluded_section_ids or set()
        self._selected_section_ids: list[int] = []
        self._loading_sections = False
        self._current_document_id: int | None = None

        self.setWindowTitle("Přidat ustanovení")
        configure_resizable_form_dialog(self, width=980, height=640, min_width=720, min_height=480)

        root = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Hledat právní předpis")
        self.search_input.textChanged.connect(self._reload_documents)
        root.addWidget(self.search_input)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.document_list = QListWidget()
        self.document_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.document_list.currentItemChanged.connect(self._on_document_selected)
        splitter.addWidget(self.document_list)

        sections_panel = QWidget()
        sections_layout = QVBoxLayout(sections_panel)
        sections_layout.setContentsMargins(0, 0, 0, 0)

        sections_toolbar = QHBoxLayout()
        self.select_all_btn = QPushButton("Označit vše zobrazené")
        self.select_all_btn.clicked.connect(self._select_all_visible)
        self.clear_all_btn = QPushButton("Odznačit vše")
        self.clear_all_btn.clicked.connect(self._clear_all_visible)
        sections_toolbar.addWidget(self.select_all_btn)
        sections_toolbar.addWidget(self.clear_all_btn)
        sections_toolbar.addStretch()
        sections_layout.addLayout(sections_toolbar)

        self.sections_tree = QTreeWidget()
        self.sections_tree.setHeaderHidden(True)
        self.sections_tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.sections_tree.itemChanged.connect(self._on_section_item_changed)
        sections_layout.addWidget(self.sections_tree, 1)

        self.sections_hint = QLabel("Vyberte právní předpis vlevo.")
        self.sections_hint.setWordWrap(True)
        sections_layout.addWidget(self.sections_hint)

        splitter.addWidget(sections_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, 1)

        self.selection_count_label = QLabel("Vybráno: 0")
        root.addWidget(self.selection_count_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.add_btn = QPushButton("Přidat vybraná")
        self.add_btn.clicked.connect(self._accept)
        self.add_btn.setEnabled(False)
        cancel_btn = QPushButton("Zrušit")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.add_btn)
        buttons.addWidget(cancel_btn)
        root.addLayout(buttons)

        self._reload_documents()

    def selected_section_id(self) -> int | None:
        section_ids = self.selected_section_ids()
        return section_ids[0] if section_ids else None

    def selected_section_ids(self) -> list[int]:
        return list(self._selected_section_ids)

    def _reload_documents(self) -> None:
        query = self.search_input.text()
        documents = legal_document_service.list_matching(query, include_inactive=False)

        previous_document_id = self._current_document_id
        self.document_list.blockSignals(True)
        self.document_list.clear()
        selected_row = -1
        for index, document in enumerate(documents):
            item = QListWidgetItem(legal_document_list_label(document))
            item.setData(Qt.ItemDataRole.UserRole, document.id)
            self.document_list.addItem(item)
            if previous_document_id is not None and document.id == previous_document_id:
                selected_row = index
        self.document_list.blockSignals(False)

        if selected_row >= 0:
            self.document_list.setCurrentRow(selected_row)
        elif self.document_list.count() == 1:
            self.document_list.setCurrentRow(0)
        elif self.document_list.count() == 0:
            self._current_document_id = None
            self._clear_sections_tree()

    def _on_document_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._current_document_id = None
            self._clear_sections_tree()
            return

        document_id = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(document_id, int):
            self._clear_sections_tree()
            return

        self._current_document_id = document_id
        self._load_sections_for_document(document_id)

    def _load_sections_for_document(self, document_id: int) -> None:
        sections = legal_section_service.list_for_document_current_version(document_id)
        self._loading_sections = True
        try:
            self.sections_tree.clear()
            if not sections:
                self.sections_hint.setText("Předpis nemá načtená ustanovení.")
                self.sections_hint.setVisible(True)
                self.sections_tree.setVisible(False)
                self._update_selection_state()
                return

            self.sections_hint.setVisible(False)
            self.sections_tree.setVisible(True)
            sections_by_id = legal_section_service.build_sections_map(sections)
            children_by_parent = build_section_children_map(sections)
            self._add_section_children(
                parent_item=None,
                child_sections=children_by_parent.get(None, []),
                children_by_parent=children_by_parent,
                sections_by_id=sections_by_id,
            )
            self.sections_tree.expandAll()
        finally:
            self._loading_sections = False
        self._update_selection_state()

    def _add_section_children(
        self,
        *,
        parent_item: QTreeWidgetItem | None,
        child_sections,
        children_by_parent: dict[int | None, list],
        sections_by_id: dict[int, object],
    ) -> None:
        for section in child_sections:
            label = legal_section_provision_label(section, sections_by_id=sections_by_id)
            if not label:
                label = (section.title or "").strip() or f"Ustanovení #{section.id}"

            item = QTreeWidgetItem([label])
            item.setData(0, _SECTION_ID_ROLE, section.id)
            selectable = LegalSectionTree.allows_requirement_creation(section.section_type)
            already_assigned = section.id in self._excluded_section_ids
            item.setData(0, _ALREADY_ASSIGNED_ROLE, already_assigned)

            if selectable:
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                )
                if already_assigned:
                    item.setCheckState(0, Qt.CheckState.Checked)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
            else:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)

            if parent_item is None:
                self.sections_tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)

            grandchildren = children_by_parent.get(section.id, [])
            if grandchildren:
                self._add_section_children(
                    parent_item=item,
                    child_sections=grandchildren,
                    children_by_parent=children_by_parent,
                    sections_by_id=sections_by_id,
                )

    def _clear_sections_tree(self) -> None:
        self._loading_sections = True
        try:
            self.sections_tree.clear()
        finally:
            self._loading_sections = False
        self.sections_hint.setText("Vyberte právní předpis vlevo.")
        self.sections_hint.setVisible(True)
        self.sections_tree.setVisible(False)
        self._update_selection_state()

    def _iter_section_items(self):
        def walk(item: QTreeWidgetItem):
            section_id = item.data(0, _SECTION_ID_ROLE)
            if isinstance(section_id, int):
                yield item
            for index in range(item.childCount()):
                yield from walk(item.child(index))

        for index in range(self.sections_tree.topLevelItemCount()):
            top = self.sections_tree.topLevelItem(index)
            if top is not None:
                yield from walk(top)

    def _iter_checkable_items(self):
        for item in self._iter_section_items():
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                yield item

    def _collect_newly_selected_section_ids(self) -> list[int]:
        selected: list[int] = []
        seen: set[int] = set()
        for item in self._iter_section_items():
            if item.data(0, _ALREADY_ASSIGNED_ROLE):
                continue
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            section_id = item.data(0, _SECTION_ID_ROLE)
            if not isinstance(section_id, int):
                continue
            if section_id in self._excluded_section_ids or section_id in seen:
                continue
            seen.add(section_id)
            selected.append(section_id)
        return selected

    def _select_all_visible(self) -> None:
        self._loading_sections = True
        try:
            for item in self._iter_checkable_items():
                if item.data(0, _ALREADY_ASSIGNED_ROLE):
                    continue
                item.setCheckState(0, Qt.CheckState.Checked)
        finally:
            self._loading_sections = False
        self._update_selection_state()

    def _clear_all_visible(self) -> None:
        self._loading_sections = True
        try:
            for item in self._iter_checkable_items():
                if item.data(0, _ALREADY_ASSIGNED_ROLE):
                    continue
                item.setCheckState(0, Qt.CheckState.Unchecked)
        finally:
            self._loading_sections = False
        self._update_selection_state()

    def _on_section_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        if self._loading_sections:
            return
        if item.data(0, _ALREADY_ASSIGNED_ROLE):
            return
        self._update_selection_state()

    def _update_selection_state(self) -> None:
        selected = self._collect_newly_selected_section_ids()
        self.selection_count_label.setText(f"Vybráno: {len(selected)}")
        self.add_btn.setEnabled(bool(selected))

    def _accept(self) -> None:
        selected = self._collect_newly_selected_section_ids()
        if not selected:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Vyberte alespoň jedno ustanovení.",
            )
            return
        self._selected_section_ids = selected
        self.accept()
