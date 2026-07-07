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
        DOCUMENT_TYPE_ZAKON,
        SECTION_DIVISION,
        SECTION_HEAD,
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_PART,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
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


def _find_item_by_paragraph(tree: LegalSectionTree, paragraph: str):
    def walk(item):
        if item.text(LegalSectionTree.COLUMN_PARAGRAPH) == paragraph:
            return item
        for index in range(item.childCount()):
            found = walk(item.child(index))
            if found is not None:
                return found
        return None

    for index in range(tree.topLevelItemCount()):
        found = walk(tree.topLevelItem(index))
        if found is not None:
            return found
    return None


def _sample_zakonik_sections():
    return [
        _section(1, section_type=SECTION_PART, sort_order=1, section_number="PRVNÍ"),
        _section(2, section_type=SECTION_HEAD, parent_section_id=1, sort_order=2, section_number="I"),
        _section(3, section_type=SECTION_DIVISION, parent_section_id=2, sort_order=3, section_number="1"),
        _section(
            4,
            section_type=SECTION_PARAGRAPH,
            parent_section_id=3,
            sort_order=4,
            paragraph="101",
            title="Předmět úpravy",
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
            section_type=SECTION_SUBSECTION,
            parent_section_id=4,
            sort_order=6,
            section_number="2",
        ),
        _section(
            7,
            section_type=SECTION_LETTER,
            parent_section_id=6,
            sort_order=7,
            item_letter="a",
        ),
        _section(
            8,
            section_type=SECTION_PARAGRAPH,
            parent_section_id=3,
            sort_order=8,
            paragraph="102",
            title="Povinnosti zaměstnance",
        ),
        _section(
            9,
            section_type=SECTION_SUBSECTION,
            parent_section_id=8,
            sort_order=9,
            section_number="1",
        ),
    ]


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
        self.assertTrue(paragraph_item.isExpanded())

    def test_sample_zakonik_structure_shows_subsections_under_paragraph_101(self) -> None:
        from PySide6.QtCore import Qt

        tree = LegalSectionTree()
        tree.load_sections(_sample_zakonik_sections())

        paragraph_item = _find_item_by_paragraph(tree, "101")
        self.assertIsNotNone(paragraph_item)
        assert paragraph_item is not None
        self.assertTrue(paragraph_item.isExpanded())
        self.assertGreaterEqual(paragraph_item.childCount(), 2)

        subsection_types = [
            paragraph_item.child(index).data(LegalSectionTree.COLUMN_TYPE, Qt.ItemDataRole.UserRole)
            for index in range(paragraph_item.childCount())
        ]
        self.assertEqual(subsection_types[:2], [SECTION_SUBSECTION, SECTION_SUBSECTION])
        self.assertEqual(paragraph_item.child(0).text(LegalSectionTree.COLUMN_NUMBER), "1")
        self.assertEqual(paragraph_item.child(1).text(LegalSectionTree.COLUMN_NUMBER), "2")

    def test_refresh_keeps_default_expansion_for_sample_zakonik(self) -> None:
        tree = LegalSectionTree()
        tree.load_sections(_sample_zakonik_sections())

        paragraph_item = _find_item_by_paragraph(tree, "101")
        assert paragraph_item is not None
        paragraph_item.setExpanded(False)
        self.assertFalse(paragraph_item.isExpanded())

        tree.load_sections(_sample_zakonik_sections())

        paragraph_item = _find_item_by_paragraph(tree, "101")
        assert paragraph_item is not None
        self.assertTrue(paragraph_item.isExpanded())
        self.assertGreaterEqual(paragraph_item.childCount(), 2)

    def test_expands_on_double_click_is_disabled(self) -> None:
        tree = LegalSectionTree()
        self.assertFalse(tree.expandsOnDoubleClick())

    def test_double_click_signal_preserves_expand_state(self) -> None:
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

        head_item = tree.topLevelItem(0).child(0)
        paragraph_item = head_item.child(0)
        self.assertTrue(head_item.isExpanded())
        self.assertTrue(paragraph_item.isExpanded())

        dialog_opened = []
        tree.itemDoubleClicked.connect(
            lambda _item, _column: dialog_opened.append(True),
        )
        tree.itemDoubleClicked.emit(paragraph_item, LegalSectionTree.COLUMN_TITLE)

        self.assertEqual(dialog_opened, [True])
        self.assertTrue(head_item.isExpanded())
        self.assertTrue(paragraph_item.isExpanded())

    def test_branch_expand_can_still_be_toggled_manually(self) -> None:
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

        paragraph_item = tree.topLevelItem(0).child(0).child(0)
        self.assertTrue(paragraph_item.isExpanded())

        paragraph_item.setExpanded(True)
        self.assertTrue(paragraph_item.isExpanded())

        paragraph_item.setExpanded(False)
        self.assertFalse(paragraph_item.isExpanded())


class LegalDocumentSectionsTabDoubleClickTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262",
            year=2006,
        )
        self.version = legal_document_version_service.create(
            legal_document_id=self.document.id,
            version_name="Aktuální znění",
        )
        self.part = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_PART,
            section_number="PRVNÍ",
            sort_order=1,
        )
        self.head = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_HEAD,
            parent_section_id=self.part.id,
            section_number="I",
            sort_order=2,
        )
        self.division = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_DIVISION,
            parent_section_id=self.head.id,
            section_number="1",
            sort_order=3,
        )
        self.paragraph = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_PARAGRAPH,
            parent_section_id=self.division.id,
            paragraph="101",
            title="Předmět",
            sort_order=4,
        )
        legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=self.paragraph.id,
            section_number="1",
            text="Text odstavce 1",
            sort_order=5,
        )
        legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=self.paragraph.id,
            section_number="2",
            text="Text odstavce 2",
            sort_order=6,
        )

    def _paragraph_item(self, tab):
        return _find_item_by_paragraph(tab.tree, "101")

    @patch("moduly.pravni_pozadavky.ui.legal_document_sections_tab.exec_maximized", return_value=False)
    @patch("moduly.pravni_pozadavky.ui.legal_document_sections_tab.LegalSectionDialog")
    def test_double_click_on_paragraph_opens_dialog(self, mock_dialog_cls, _mock_exec) -> None:
        from moduly.pravni_pozadavky.ui.legal_document_sections_tab import LegalDocumentSectionsTab

        tab = LegalDocumentSectionsTab(
            document_id=self.document.id,
            version_id=self.version.id,
        )
        paragraph_item = self._paragraph_item(tab)
        tab.tree.setCurrentItem(paragraph_item)

        head_item = paragraph_item.parent()
        expanded_before = {
            tab.tree.topLevelItem(0).isExpanded(),
            head_item.isExpanded(),
            paragraph_item.isExpanded(),
        }

        tab._on_item_double_clicked(paragraph_item, LegalSectionTree.COLUMN_TITLE)

        mock_dialog_cls.assert_called_once()
        expanded_after = {
            tab.tree.topLevelItem(0).isExpanded(),
            head_item.isExpanded(),
            paragraph_item.isExpanded(),
        }
        self.assertEqual(expanded_after, expanded_before)

    @patch("moduly.pravni_pozadavky.ui.legal_document_sections_tab.exec_maximized", return_value=True)
    @patch("moduly.pravni_pozadavky.ui.legal_document_sections_tab.LegalRequirementDialog")
    def test_refresh_after_requirement_creation_keeps_usable_expansion(
        self,
        mock_dialog_cls,
        _mock_exec,
    ) -> None:
        from moduly.pravni_pozadavky.ui.legal_document_sections_tab import LegalDocumentSectionsTab

        mock_dialog = mock_dialog_cls.return_value
        mock_dialog.get_data.return_value = {
            "regulation_name": "Předmět",
            "regulation_number": "262/2006 Sb.",
            "provision": "§ 101",
            "legal_document_id": self.document.id,
            "legal_section_id": self.paragraph.id,
            "source_section_id": self.paragraph.id,
            "area": "",
            "requirement_summary": "Nový požadavek",
            "organization_impact": "",
            "responsible_person_id": None,
            "verification_periodicity": "",
            "last_verification_date": None,
            "next_verification_date": None,
            "compliance_status": "",
            "processing_status": "new",
            "note": "",
            "active": True,
        }

        tab = LegalDocumentSectionsTab(
            document_id=self.document.id,
            version_id=self.version.id,
        )
        paragraph_item = self._paragraph_item(tab)
        assert paragraph_item is not None
        tab.tree.setCurrentItem(paragraph_item)
        self.assertTrue(paragraph_item.isExpanded())
        self.assertGreaterEqual(paragraph_item.childCount(), 2)

        tab.create_requirement_from_section()

        paragraph_item = self._paragraph_item(tab)
        assert paragraph_item is not None
        self.assertTrue(paragraph_item.isExpanded())
        self.assertGreaterEqual(paragraph_item.childCount(), 2)
        self.assertEqual(paragraph_item.child(0).text(LegalSectionTree.COLUMN_NUMBER), "1")


if __name__ == "__main__":
    unittest.main()
