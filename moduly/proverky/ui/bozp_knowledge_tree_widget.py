"""Levý panel znalostního stromu prověrek BOZP."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from moduly.proverky.constants import AREA_PANEL_LEFT_WIDTH
from moduly.proverky.sluzby.proverky_knowledge_service import (
    KNOWLEDGE_NODE_AREA,
    KNOWLEDGE_NODE_SECTION,
    KnowledgeTreeNode,
    proverky_knowledge_service,
)


class BozpKnowledgeTreeWidget(QTreeWidget):
    section_selected = Signal(object)
    area_selected = Signal(object)

    _ROLE_NODE_TYPE = Qt.ItemDataRole.UserRole
    _ROLE_NODE_ID = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)

        self._roots: list[KnowledgeTreeNode] = []
        self._nodes_by_item: dict[int, KnowledgeTreeNode] = {}

        self.setHeaderHidden(True)
        self.setAlternatingRowColors(True)
        self.setMinimumWidth(AREA_PANEL_LEFT_WIDTH)
        self.setIndentation(22)
        self.setExpandsOnDoubleClick(True)
        self.currentItemChanged.connect(self._on_current_item_changed)

    @property
    def tree_roots(self) -> list[KnowledgeTreeNode]:
        return list(self._roots)

    def reload_tree(self, *, include_inactive: bool = False) -> None:
        self._roots = proverky_knowledge_service.get_knowledge_tree(
            include_inactive=include_inactive,
        )
        self.blockSignals(True)
        self.clear()
        self._nodes_by_item.clear()

        for root in self._roots:
            area_item = self._create_item(root)
            self.addTopLevelItem(area_item)
            self._append_children(area_item, root.children)
            area_item.setExpanded(True)

        self.blockSignals(False)
        self.clearSelection()
        self.setCurrentItem(None)
        self.scrollToTop()
        self.section_selected.emit(None)

    def select_node(self, area_id: str, section_id: str | None = None) -> bool:
        for index in range(self.topLevelItemCount()):
            area_item = self.topLevelItem(index)
            node = self.node_for_item(area_item)
            if node is None or node.area_id != area_id:
                continue

            if not section_id:
                self.setCurrentItem(area_item)
                return True

            section_item = self._find_section_item(area_item, section_id)
            if section_item is not None:
                self.setCurrentItem(section_item)
                return True

        return False

    def _find_section_item(
        self,
        parent_item: QTreeWidgetItem,
        section_id: str,
    ) -> QTreeWidgetItem | None:
        for index in range(parent_item.childCount()):
            child_item = parent_item.child(index)
            node = self.node_for_item(child_item)
            if node is not None and node.node_id == section_id:
                return child_item

            nested = self._find_section_item(child_item, section_id)
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
        if node.node_type == KNOWLEDGE_NODE_AREA:
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
            self.section_selected.emit(None)
            return

        if node.node_type == KNOWLEDGE_NODE_AREA:
            self.area_selected.emit(node)
            self.section_selected.emit(None)
            return

        if node.node_type == KNOWLEDGE_NODE_SECTION:
            self.section_selected.emit(node)
