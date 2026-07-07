from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem

from moduly.pravni_pozadavky.constants import (
    SECTION_HEAD,
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_PART,
    SECTION_SUBSECTION,
    SECTION_TYPE_LABELS,
)


def build_section_children_map(sections) -> dict[int | None, list]:
    children_by_parent: dict[int | None, list] = {}
    for section in sections:
        parent_id = getattr(section, "parent_section_id", None)
        children_by_parent.setdefault(parent_id, []).append(section)

    for child_list in children_by_parent.values():
        child_list.sort(key=lambda item: (item.sort_order, item.id))
    return children_by_parent


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
    ) -> None:
        requirement_section_ids = sections_with_requirements or set()
        self.clear()
        children_by_parent = build_section_children_map(sections)
        self._add_children(
            parent_item=None,
            child_sections=children_by_parent.get(None, []),
            children_by_parent=children_by_parent,
            sections_with_requirements=requirement_section_ids,
        )
        self._apply_expand_state()

    def _add_children(
        self,
        *,
        parent_item: QTreeWidgetItem | None,
        child_sections,
        children_by_parent: dict[int | None, list],
        sections_with_requirements: set[int],
    ) -> None:
        for section in child_sections:
            item = self._create_item(section, sections_with_requirements)
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
                    sections_with_requirements=sections_with_requirements,
                )

    def _create_item(self, section, sections_with_requirements: set[int]) -> QTreeWidgetItem:
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
            "Ano" if section.id in sections_with_requirements else "Ne",
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
            top_item = self.topLevelItem(index)
            self._expand_matching(top_item, {SECTION_PART, SECTION_HEAD})
            self._collapse_paragraphs(top_item)

    def _expand_matching(self, item: QTreeWidgetItem, section_types: set[str]) -> None:
        section_type = item.data(self.COLUMN_TYPE, Qt.ItemDataRole.UserRole)
        if section_type in section_types:
            item.setExpanded(True)
        for child_index in range(item.childCount()):
            self._expand_matching(item.child(child_index), section_types)

    def _collapse_paragraphs(self, item: QTreeWidgetItem) -> None:
        section_type = item.data(self.COLUMN_TYPE, Qt.ItemDataRole.UserRole)
        if section_type == SECTION_PARAGRAPH:
            item.setExpanded(False)
        for child_index in range(item.childCount()):
            self._collapse_paragraphs(item.child(child_index))

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
