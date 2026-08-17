"""Levý panel stromu auditovaných procesů."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from moduly.audity.constants import PROCESS_PANEL_LEFT_WIDTH
from moduly.audity.sluzby.audit_knowledge_service import (
    KNOWLEDGE_NODE_PROCESS,
    KNOWLEDGE_NODE_SECTION,
    AuditCatalogError,
    KnowledgeTreeNode,
    audit_knowledge_service,
)


class AuditKnowledgeTreeWidget(QTreeWidget):
    criterion_selected = Signal(object)
    process_selected = Signal(object)
    catalog_error = Signal(str)

    _ROLE_NODE_TYPE = Qt.ItemDataRole.UserRole
    _ROLE_NODE_ID = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)

        self._roots: list[KnowledgeTreeNode] = []
        self._nodes_by_item: dict[int, KnowledgeTreeNode] = {}
        self._catalog_error: str | None = None

        self.setHeaderHidden(True)
        self.setAlternatingRowColors(True)
        self.setMinimumWidth(PROCESS_PANEL_LEFT_WIDTH)
        self.setIndentation(22)
        self.setExpandsOnDoubleClick(True)
        self.currentItemChanged.connect(self._on_current_item_changed)

    @property
    def catalog_error_message(self) -> str | None:
        return self._catalog_error

    @property
    def tree_roots(self) -> list[KnowledgeTreeNode]:
        return list(self._roots)

    def reload_tree(
        self,
        *,
        include_inactive: bool = False,
        ensure: bool = True,
        process_ids: set[str] | None = None,
        roots: list[KnowledgeTreeNode] | tuple[KnowledgeTreeNode, ...] | None = None,
    ) -> None:
        self._include_inactive = include_inactive
        self._process_filter = process_ids
        self._catalog_error = None
        try:
            if roots is not None:
                # Snapshot / přednačtený strom — bez živé metodiky.
                self._roots = list(roots)
            else:
                self._roots = audit_knowledge_service.get_knowledge_tree(
                    include_inactive=include_inactive,
                    ensure=ensure,
                )
        except AuditCatalogError as exc:
            self._roots = []
            self._catalog_error = str(exc)
            self.catalog_error.emit(self._catalog_error)

        self.blockSignals(True)
        self.clear()
        self._nodes_by_item.clear()

        for root in self._roots:
            if process_ids and root.process_id not in process_ids:
                continue
            process_item = self._create_item(root)
            self.addTopLevelItem(process_item)
            self._append_children(process_item, root.children)
            process_item.setExpanded(True)

        self.blockSignals(False)
        self.clearSelection()
        self.criterion_selected.emit(None)

    def select_node(self, process_id: str, criterion_id: str | None = None) -> bool:
        for index in range(self.topLevelItemCount()):
            process_item = self.topLevelItem(index)
            node = self.node_for_item(process_item)
            if node is None or node.process_id != process_id:
                continue

            if not criterion_id:
                self.setCurrentItem(process_item)
                return True

            criterion_item = self._find_criterion_item(process_item, criterion_id)
            if criterion_item is not None:
                self.setCurrentItem(criterion_item)
                return True

        return False

    def _find_criterion_item(
        self,
        parent_item: QTreeWidgetItem,
        criterion_id: str,
    ) -> QTreeWidgetItem | None:
        for index in range(parent_item.childCount()):
            child_item = parent_item.child(index)
            node = self.node_for_item(child_item)
            if node is not None and node.node_id == criterion_id:
                return child_item

            nested = self._find_criterion_item(child_item, criterion_id)
            if nested is not None:
                return nested

        return None

    def node_for_item(self, item: QTreeWidgetItem | None) -> KnowledgeTreeNode | None:
        if item is None:
            return None
        return self._nodes_by_item.get(id(item))

    def _append_children(self, parent_item: QTreeWidgetItem, nodes: tuple[KnowledgeTreeNode, ...]) -> None:
        for node in nodes:
            child_item = self._create_item(node)
            parent_item.addChild(child_item)
            if node.children:
                self._append_children(child_item, node.children)

    def _create_item(self, node: KnowledgeTreeNode) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.label])
        item.setData(0, self._ROLE_NODE_TYPE, node.node_type)
        item.setData(0, self._ROLE_NODE_ID, node.node_id)
        if node.node_type == KNOWLEDGE_NODE_PROCESS:
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
        self._nodes_by_item[id(item)] = node
        return item

    def _on_current_item_changed(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None,
    ) -> None:
        node = self.node_for_item(current)
        if node is None:
            self.criterion_selected.emit(None)
            return

        if node.node_type == KNOWLEDGE_NODE_PROCESS:
            self.process_selected.emit(node)
            self.criterion_selected.emit(None)
            return

        if node.node_type == KNOWLEDGE_NODE_SECTION:
            self.criterion_selected.emit(node)
