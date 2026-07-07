from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem

from moduly.pravni_pozadavky.constants import (
    REQUIREMENT_STATUS_APPROVED,
    REQUIREMENT_STATUS_EXISTS,
    REQUIREMENT_TREE_ICON_APPROVED,
    REQUIREMENT_TREE_ICON_EXISTS,
    REQUIREMENT_TREE_ICON_NONE,
    SECTION_DIVISION,
    SECTION_HEAD,
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_PART,
    SECTION_SUBSECTION,
    SECTION_TYPE_LABELS,
)

_DEFAULT_EXPANDED_TYPES = frozenset({
    SECTION_PART,
    SECTION_HEAD,
    SECTION_DIVISION,
    SECTION_PARAGRAPH,
})


def build_section_children_map(sections) -> dict[int | None, list]:
    children_by_parent: dict[int | None, list] = {}
    for section in sections:
        parent_id = getattr(section, "parent_section_id", None)
        children_by_parent.setdefault(parent_id, []).append(section)

    for child_list in children_by_parent.values():
        child_list.sort(key=lambda item: (item.sort_order, item.id))
    return children_by_parent


def ordered_processable_sections(sections) -> list:
    return sorted(
        [
            section
            for section in sections
            if section.active and LegalSectionTree.allows_requirement_creation(section.section_type)
        ],
        key=lambda item: (item.sort_order, item.id),
    )


def next_processable_section(sections, current_section_id: int):
    ordered = ordered_processable_sections(sections)
    for index, section in enumerate(ordered):
        if section.id == current_section_id and index + 1 < len(ordered):
            return ordered[index + 1]
    return None


def requirement_tree_icon(section, section_requirement_statuses: dict[int, str]) -> str:
    if not LegalSectionTree.allows_requirement_creation(section.section_type):
        return ""
    status = section_requirement_statuses.get(section.id)
    if status == REQUIREMENT_STATUS_APPROVED:
        return REQUIREMENT_TREE_ICON_APPROVED
    if status == REQUIREMENT_STATUS_EXISTS:
        return REQUIREMENT_TREE_ICON_EXISTS
    return REQUIREMENT_TREE_ICON_NONE


class LegalSectionTree(QTreeWidget):
    COLUMN_ID = 0
    COLUMN_TYPE = 1
    COLUMN_NUMBER = 2
    COLUMN_PARAGRAPH = 3
    COLUMN_LETTER = 4
    COLUMN_TITLE = 5
    COLUMN_SORT_ORDER = 6
    COLUMN_ACTIVE = 7
    COLUMN_REQUIREMENT = 8

    def __init__(self):
        super().__init__()

        self.setColumnCount(9)
        self.setHeaderLabels([
            "ID",
            "Typ",
            "Číslo",
            "§",
            "Písmeno",
            "Název",
            "Pořadí",
            "Aktivní",
            "Požadavek",
        ])

        self.setColumnHidden(self.COLUMN_ID, True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.setUniformRowHeights(False)
        self.setExpandsOnDoubleClick(False)

        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(self.COLUMN_TITLE, QHeaderView.ResizeMode.Stretch)
        for column in (
            self.COLUMN_TYPE,
            self.COLUMN_NUMBER,
            self.COLUMN_PARAGRAPH,
            self.COLUMN_LETTER,
            self.COLUMN_SORT_ORDER,
            self.COLUMN_ACTIVE,
            self.COLUMN_REQUIREMENT,
        ):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(self.COLUMN_TYPE, 100)
        self.setColumnWidth(self.COLUMN_NUMBER, 70)
        self.setColumnWidth(self.COLUMN_PARAGRAPH, 50)
        self.setColumnWidth(self.COLUMN_LETTER, 70)
        self.setColumnWidth(self.COLUMN_SORT_ORDER, 70)
        self.setColumnWidth(self.COLUMN_ACTIVE, 80)
        self.setColumnWidth(self.COLUMN_REQUIREMENT, 90)

    def load_sections(
        self,
        sections,
        *,
        sections_with_requirements: set[int] | None = None,
        section_requirement_statuses: dict[int, str] | None = None,
    ) -> None:
        resolved_statuses = section_requirement_statuses
        if resolved_statuses is None and sections_with_requirements:
            resolved_statuses = {
                section_id: REQUIREMENT_STATUS_EXISTS
                for section_id in sections_with_requirements
            }
        requirement_statuses = resolved_statuses or {}
        self.clear()
        children_by_parent = build_section_children_map(sections)
        self._add_children(
            parent_item=None,
            child_sections=children_by_parent.get(None, []),
            children_by_parent=children_by_parent,
            section_requirement_statuses=requirement_statuses,
        )
        self._apply_expand_state()

    def _add_children(
        self,
        *,
        parent_item: QTreeWidgetItem | None,
        child_sections,
        children_by_parent: dict[int | None, list],
        section_requirement_statuses: dict[int, str],
    ) -> None:
        for section in child_sections:
            item = self._create_item(section, section_requirement_statuses)
            if parent_item is None:
                self.addTopLevelItem(item)
            else:
                parent_item.addChild(item)

            grandchildren = children_by_parent.get(section.id, [])
            if grandchildren:
                self._add_children(
                    parent_item=item,
                    child_sections=grandchildren,
                    children_by_parent=children_by_parent,
                    section_requirement_statuses=section_requirement_statuses,
                )

    def _create_item(self, section, section_requirement_statuses: dict[int, str]) -> QTreeWidgetItem:
        section_type = SECTION_TYPE_LABELS.get(
            section.section_type,
            section.section_type,
        )
        item = QTreeWidgetItem([
            str(section.id),
            section_type,
            section.section_number or "",
            section.paragraph or "",
            section.item_letter or "",
            section.title or "",
            str(section.sort_order),
            "Ano" if section.active else "Ne",
            requirement_tree_icon(section, section_requirement_statuses),
        ])
        item.setData(self.COLUMN_ID, Qt.ItemDataRole.UserRole, section.id)
        item.setData(self.COLUMN_TYPE, Qt.ItemDataRole.UserRole, section.section_type)

        if not section.active:
            brush = QBrush(QColor("#f0f0f0"))
            for column in range(self.columnCount()):
                item.setBackground(column, brush)
        return item

    def _apply_expand_state(self) -> None:
        for index in range(self.topLevelItemCount()):
            self._expand_matching(self.topLevelItem(index), _DEFAULT_EXPANDED_TYPES)

    def _expand_matching(self, item: QTreeWidgetItem, section_types: set[str]) -> None:
        section_type = item.data(self.COLUMN_TYPE, Qt.ItemDataRole.UserRole)
        if section_type in section_types:
            item.setExpanded(True)
        for child_index in range(item.childCount()):
            self._expand_matching(item.child(child_index), section_types)

    def selected_section_id(self) -> int | None:
        selected_items = self.selectedItems()
        if not selected_items:
            return None
        section_id = selected_items[0].data(self.COLUMN_ID, Qt.ItemDataRole.UserRole)
        return int(section_id) if section_id is not None else None

    def selected_section_type(self) -> str | None:
        selected_items = self.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].data(self.COLUMN_TYPE, Qt.ItemDataRole.UserRole)

    @staticmethod
    def allows_requirement_creation(section_type: str | None) -> bool:
        return section_type in {
            SECTION_PARAGRAPH,
            SECTION_SUBSECTION,
            SECTION_LETTER,
        }

    def top_level_section_types(self) -> list[str]:
        return [
            self.topLevelItem(index).data(self.COLUMN_TYPE, Qt.ItemDataRole.UserRole)
            for index in range(self.topLevelItemCount())
        ]

    def find_item_by_section_id(self, section_id: int) -> QTreeWidgetItem | None:
        def walk(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            if item.data(self.COLUMN_ID, Qt.ItemDataRole.UserRole) == section_id:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self.topLevelItemCount()):
            found = walk(self.topLevelItem(index))
            if found is not None:
                return found
        return None

    def select_section_id(self, section_id: int) -> bool:
        item = self.find_item_by_section_id(section_id)
        if item is None:
            return False
        self.setCurrentItem(item)
        return True
