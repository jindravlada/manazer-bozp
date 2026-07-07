import importlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.pravni_pozadavky.constants import (
        SECTION_DIVISION,
        SECTION_HEAD,
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_PART,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.ui.legal_section_tree import (
        LegalSectionTree,
        build_section_children_map,
    )


def _section(
    section_id: int,
    *,
    section_type: str,
    parent_section_id: int | None = None,
    sort_order: int = 0,
    title: str = "",
    paragraph: str = "",
    section_number: str = "",
    item_letter: str = "",
    active: bool = True,
):
    return SimpleNamespace(
        id=section_id,
        section_type=section_type,
        parent_section_id=parent_section_id,
        sort_order=sort_order,
        title=title,
        paragraph=paragraph,
        section_number=section_number,
        item_letter=item_letter,
        active=active,
        text="",
    )


class LegalSectionTreeUtilsTestCase(unittest.TestCase):
    def test_build_section_children_map_creates_hierarchy(self) -> None:
        sections = [
            _section(1, section_type=SECTION_PART, sort_order=1, section_number="PRVNÍ"),
            _section(2, section_type=SECTION_HEAD, parent_section_id=1, sort_order=2, section_number="I"),
            _section(3, section_type=SECTION_DIVISION, parent_section_id=2, sort_order=3, section_number="1"),
            _section(
                4,
                section_type=SECTION_PARAGRAPH,
                parent_section_id=3,
                sort_order=4,
                paragraph="101",
                title="Předmět",
            ),
            _section(
                5,
                section_type=SECTION_SUBSECTION,
                parent_section_id=4,
                sort_order=5,
                section_number="1",
            ),
            _section(
                6,
                section_type=SECTION_LETTER,
                parent_section_id=5,
                sort_order=6,
                item_letter="a",
            ),
        ]

        children_map = build_section_children_map(sections)

        self.assertEqual([item.id for item in children_map[None]], [1])
        self.assertEqual([item.id for item in children_map[1]], [2])
        self.assertEqual([item.id for item in children_map[2]], [3])
        self.assertEqual([item.id for item in children_map[3]], [4])
        self.assertEqual([item.id for item in children_map[4]], [5])
        self.assertEqual([item.id for item in children_map[5]], [6])

    def test_allows_requirement_creation_only_for_leaf_types(self) -> None:
        self.assertTrue(LegalSectionTree.allows_requirement_creation(SECTION_PARAGRAPH))
        self.assertTrue(LegalSectionTree.allows_requirement_creation(SECTION_SUBSECTION))
        self.assertTrue(LegalSectionTree.allows_requirement_creation(SECTION_LETTER))
        self.assertFalse(LegalSectionTree.allows_requirement_creation(SECTION_PART))
        self.assertFalse(LegalSectionTree.allows_requirement_creation(SECTION_HEAD))
        self.assertFalse(LegalSectionTree.allows_requirement_creation(SECTION_DIVISION))


class LegalSectionTreeWidgetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_tree_widget_builds_root_and_nested_items(self) -> None:
        from PySide6.QtCore import Qt

        sections = [
            _section(1, section_type=SECTION_PART, sort_order=1, section_number="PRVNÍ"),
            _section(2, section_type=SECTION_HEAD, parent_section_id=1, sort_order=2, section_number="I"),
            _section(
                3,
                section_type=SECTION_PARAGRAPH,
                parent_section_id=2,
                sort_order=3,
                paragraph="101",
                title="Předmět",
            ),
        ]

        tree = LegalSectionTree()
        tree.load_sections(sections)

        self.assertEqual(tree.topLevelItemCount(), 1)
        root = tree.topLevelItem(0)
        self.assertEqual(root.data(LegalSectionTree.COLUMN_ID, Qt.ItemDataRole.UserRole), 1)
        self.assertEqual(root.childCount(), 1)
        head_item = root.child(0)
        self.assertEqual(head_item.data(LegalSectionTree.COLUMN_TYPE, Qt.ItemDataRole.UserRole), SECTION_HEAD)
        self.assertTrue(head_item.isExpanded())
        self.assertEqual(head_item.childCount(), 1)
        paragraph_item = head_item.child(0)
        self.assertEqual(
            paragraph_item.data(LegalSectionTree.COLUMN_TYPE, Qt.ItemDataRole.UserRole),
            SECTION_PARAGRAPH,
        )
        self.assertFalse(paragraph_item.isExpanded())


if __name__ == "__main__":
    unittest.main()
