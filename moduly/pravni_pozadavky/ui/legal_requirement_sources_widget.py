from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from moduly.pravni_pozadavky.constants import (
    legal_document_regulation_number,
    legal_section_provision_label,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_requirement_source_add_dialog import (
    LegalRequirementSourceAddDialog,
)

_SECTION_ID_ROLE = Qt.ItemDataRole.UserRole
_DOCUMENT_ID_ROLE = Qt.ItemDataRole.UserRole + 1
_NO_SOURCE_SELECTED_TEXT = "Nejprve vyberte právní podklad."
_MISSING_SECTION_TEXT = "Znění ustanovení není k dispozici."


class LegalRequirementSourcesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat ustanovení")
        self.remove_btn = QPushButton("Odebrat")
        self.remove_btn.setEnabled(False)
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.remove_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.setMinimumHeight(300)
        layout.addWidget(self.tree, 1)

        self.add_btn.clicked.connect(self._add_source)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.tree.itemSelectionChanged.connect(self._update_buttons)
        self.tree.itemClicked.connect(self._on_item_clicked)

    def load_section_ids(self, section_ids: list[int]) -> None:
        self.tree.clear()
        document_order: list[int] = []
        sections_by_document: dict[int, list[int]] = {}

        for section_id in section_ids:
            section = legal_section_service.get_by_id(section_id)
            if section is None:
                continue
            document_id = section.legal_document_id
            if document_id not in sections_by_document:
                document_order.append(document_id)
                sections_by_document[document_id] = []
            if section_id not in sections_by_document[document_id]:
                sections_by_document[document_id].append(section_id)

        for document_id in document_order:
            root = self._find_or_create_document_root(document_id)
            for section_id in sections_by_document[document_id]:
                self._append_section_item(root, section_id)

        self.tree.expandAll()
        self.select_first_row()

    def get_section_ids(self) -> list[int]:
        section_ids: list[int] = []
        for item in self._section_items_in_order():
            section_id = item.data(0, _SECTION_ID_ROLE)
            if isinstance(section_id, int) and section_id not in section_ids:
                section_ids.append(section_id)
        return section_ids

    def selected_section_id(self) -> int | None:
        item = self.tree.currentItem()
        if item is None or self._is_root_item(item):
            return None
        section_id = item.data(0, _SECTION_ID_ROLE)
        return section_id if isinstance(section_id, int) else None

    def select_first_row(self) -> None:
        first_section = self._first_section_item()
        if first_section is not None:
            self.tree.setCurrentItem(first_section)
        else:
            self.tree.clearSelection()

    def select_section_at_index(self, index: int) -> None:
        items = self._section_items_in_order()
        if 0 <= index < len(items):
            self.tree.setCurrentItem(items[index])
        else:
            self.tree.clearSelection()

    def _document_tree_label(self, document) -> str:
        regulation_number = legal_document_regulation_number(document)
        title = (document.title or "").strip()
        if title:
            return f"{regulation_number} – {title}"
        return regulation_number

    def _find_or_create_document_root(self, document_id: int) -> QTreeWidgetItem:
        for index in range(self.tree.topLevelItemCount()):
            root = self.tree.topLevelItem(index)
            if root is not None and root.data(0, _DOCUMENT_ID_ROLE) == document_id:
                return root

        document = legal_document_service.get_by_id(document_id)
        label = self._document_tree_label(document) if document is not None else f"Předpis #{document_id}"
        root = QTreeWidgetItem([label])
        root.setData(0, _DOCUMENT_ID_ROLE, document_id)
        self.tree.addTopLevelItem(root)
        return root

    def _append_section_item(self, root: QTreeWidgetItem, section_id: int) -> QTreeWidgetItem | None:
        section = legal_section_service.get_by_id(section_id)
        if section is None:
            return None

        sections_by_id = legal_section_service.build_sections_map([section])
        provision_label = legal_section_provision_label(section, sections_by_id=sections_by_id)
        if not provision_label:
            provision_label = f"Ustanovení #{section.id}"

        item = QTreeWidgetItem([provision_label])
        item.setData(0, _SECTION_ID_ROLE, section_id)
        root.addChild(item)
        return item

    def _append_section(self, section_id: int) -> None:
        section = legal_section_service.get_by_id(section_id)
        if section is None:
            return

        root = self._find_or_create_document_root(section.legal_document_id)
        self._append_section_item(root, section_id)
        root.setExpanded(True)

        items = self._section_items_in_order()
        for item in items:
            if item.data(0, _SECTION_ID_ROLE) == section_id:
                self.tree.setCurrentItem(item)
                break

    def _add_source(self) -> None:
        dialog = LegalRequirementSourceAddDialog(
            self,
            excluded_section_ids=set(self.get_section_ids()),
        )
        if exec_maximized(dialog) != LegalRequirementSourceAddDialog.DialogCode.Accepted:
            return

        section_id = dialog.selected_section_id()
        if section_id is None:
            return
        if section_id in self.get_section_ids():
            QMessageBox.information(
                self,
                "Právní podklad",
                "Toto ustanovení je již přidáno.",
            )
            return
        self._append_section(section_id)

    def _remove_selected(self) -> None:
        item = self.tree.currentItem()
        if item is None or self._is_root_item(item):
            return

        parent = item.parent()
        index = parent.indexOfChild(item)
        parent.takeChild(index)
        if parent.childCount() == 0:
            root_index = self.tree.indexOfTopLevelItem(parent)
            if root_index >= 0:
                self.tree.takeTopLevelItem(root_index)
        self._update_buttons()

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if self._is_root_item(item):
            item.setExpanded(not item.isExpanded())

    def _is_root_item(self, item: QTreeWidgetItem | None) -> bool:
        return item is not None and item.parent() is None

    def _section_items_in_order(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []
        for root_index in range(self.tree.topLevelItemCount()):
            root = self.tree.topLevelItem(root_index)
            if root is None:
                continue
            for child_index in range(root.childCount()):
                child = root.child(child_index)
                if child is not None:
                    items.append(child)
        return items

    def _first_section_item(self) -> QTreeWidgetItem | None:
        items = self._section_items_in_order()
        return items[0] if items else None

    def _update_buttons(self) -> None:
        item = self.tree.currentItem()
        self.remove_btn.setEnabled(item is not None and not self._is_root_item(item))
