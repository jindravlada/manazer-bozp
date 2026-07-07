import importlib
import os
import tempfile
import unittest
from pathlib import Path
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
        PERIODICITY_ROCNE,
        PROCESSING_APPROVED,
        PROCESSING_NEW,
        REQUIREMENT_STATUS_APPROVED,
        REQUIREMENT_STATUS_EXISTS,
        REQUIREMENT_TREE_ICON_APPROVED,
        REQUIREMENT_TREE_ICON_EXISTS,
        REQUIREMENT_TREE_ICON_NONE,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_document_workbench_tab import LegalDocumentWorkbenchTab
    from moduly.pravni_pozadavky.ui.legal_section_tree import (
        LegalSectionTree,
        next_processable_section,
        ordered_processable_sections,
    )


class LegalRequirementWorkbenchServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for requirement in legal_requirement_service.get_all():
            requirement.active = False
            legal_requirement_service.repository.update(requirement)

    def _create_document(self):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )

    def _create_version(self, document):
        return legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )

    def _create_processable_sections(self, document, version, count: int):
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="Předmět",
            sort_order=1,
        )
        sections = []
        for index in range(1, count + 1):
            sections.append(
                legal_section_service.create(
                    legal_document_id=document.id,
                    legal_document_version_id=version.id,
                    section_type=SECTION_SUBSECTION,
                    parent_section_id=paragraph.id,
                    section_number=str(index),
                    text=f"Text odstavce {index}",
                    sort_order=index,
                )
            )
        return sections

    def test_get_source_section_requirement_statuses(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        sections = self._create_processable_sections(document, version, 2)

        legal_requirement_service.create_requirement(
            regulation_name="Požadavek 1",
            legal_document_id=document.id,
            legal_section_id=sections[0].id,
            source_section_id=sections[0].id,
            requirement_summary="Text 1",
            processing_status=PROCESSING_NEW,
        )
        legal_requirement_service.create_requirement(
            regulation_name="Požadavek 2",
            legal_document_id=document.id,
            legal_section_id=sections[1].id,
            source_section_id=sections[1].id,
            requirement_summary="Text 2",
            processing_status=PROCESSING_APPROVED,
        )

        statuses = legal_requirement_service.get_source_section_requirement_statuses(
            [section.id for section in sections],
        )
        self.assertEqual(statuses[sections[0].id], REQUIREMENT_STATUS_EXISTS)
        self.assertEqual(statuses[sections[1].id], REQUIREMENT_STATUS_APPROVED)

    def test_next_processable_section_follows_sort_order(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        sections = self._create_processable_sections(document, version, 3)
        all_sections = legal_section_service.list_by_version(version.id)

        ordered = ordered_processable_sections(all_sections)
        subsection_ids = [item.id for item in ordered if item.section_type == SECTION_SUBSECTION]
        self.assertEqual(subsection_ids, [section.id for section in sections])

        next_section = next_processable_section(all_sections, sections[0].id)
        assert next_section is not None
        self.assertEqual(next_section.id, sections[1].id)

        last_next = next_processable_section(all_sections, sections[2].id)
        self.assertIsNone(last_next)


class LegalRequirementWorkbenchWidgetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for requirement in legal_requirement_service.get_all():
            requirement.active = False
            legal_requirement_service.repository.update(requirement)

    def _create_document(self):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )

    def _create_version(self, document):
        return legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )

    def _create_processable_sections(self, document, version, count: int):
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="Předmět",
            sort_order=1,
        )
        sections = []
        for index in range(1, count + 1):
            sections.append(
                legal_section_service.create(
                    legal_document_id=document.id,
                    legal_document_version_id=version.id,
                    section_type=SECTION_SUBSECTION,
                    parent_section_id=paragraph.id,
                    section_number=str(index),
                    text=f"Text odstavce {index}",
                    sort_order=index,
                )
            )
        return sections

    def test_tree_shows_requirement_icons(self) -> None:
        from PySide6.QtCore import Qt

        document = self._create_document()
        version = self._create_version(document)
        sections = self._create_processable_sections(document, version, 2)
        legal_requirement_service.create_requirement(
            regulation_name="Nový",
            legal_document_id=document.id,
            legal_section_id=sections[0].id,
            source_section_id=sections[0].id,
            requirement_summary="Text",
            processing_status=PROCESSING_NEW,
        )
        legal_requirement_service.create_requirement(
            regulation_name="Schválený",
            legal_document_id=document.id,
            legal_section_id=sections[1].id,
            source_section_id=sections[1].id,
            requirement_summary="Text",
            processing_status=PROCESSING_APPROVED,
        )

        all_sections = legal_section_service.list_by_version(version.id)
        statuses = legal_requirement_service.get_source_section_requirement_statuses(
            [section.id for section in all_sections],
        )
        tree = LegalSectionTree()
        tree.load_sections(all_sections, section_requirement_statuses=statuses)

        def walk(item):
            section_id = item.data(LegalSectionTree.COLUMN_ID, Qt.ItemDataRole.UserRole)
            icons[section_id] = item.text(LegalSectionTree.COLUMN_REQUIREMENT)
            for index in range(item.childCount()):
                walk(item.child(index))

        icons = {}
        for index in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(index))

        self.assertEqual(icons[sections[0].id], REQUIREMENT_TREE_ICON_EXISTS)
        self.assertEqual(icons[sections[1].id], REQUIREMENT_TREE_ICON_APPROVED)

    def test_click_loads_new_requirement_with_section_text_prefill(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        sections = self._create_processable_sections(document, version, 1)
        section = sections[0]

        tab = LegalDocumentWorkbenchTab(document_id=document.id, version_id=version.id)
        tab.tree.select_section_id(section.id)
        tab.load_section(section.id)

        assert tab.editor is not None
        self.assertEqual(tab.editor.regulation_name.text(), "")
        self.assertEqual(tab.editor.requirement_summary.toPlainText(), section.text)

        tab.editor.regulation_name.setText("Interní povinnost BOZP")
        tab.editor.requirement_summary.setPlainText("Upravený text požadavku")
        requirement_id = tab.save_current()
        self.assertIsNotNone(requirement_id)

        tab.load_section(section.id)
        self.assertEqual(tab.editor.regulation_name.text(), "Interní povinnost BOZP")
        self.assertEqual(tab.editor.requirement_summary.toPlainText(), "Upravený text požadavku")

    def test_click_loads_existing_requirement_without_dialog(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        sections = self._create_processable_sections(document, version, 1)
        section = sections[0]
        legal_requirement_service.create_requirement(
            regulation_name="Existující",
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
            requirement_summary="Uložený text",
            area="BOZP",
            verification_periodicity=PERIODICITY_ROCNE,
            note="Poznámka",
        )

        tab = LegalDocumentWorkbenchTab(document_id=document.id, version_id=version.id)
        tab.tree.select_section_id(section.id)
        tab.load_section(section.id)

        assert tab.editor is not None
        self.assertEqual(tab.editor.regulation_name.text(), "Existující")
        self.assertEqual(tab.editor.requirement_summary.toPlainText(), "Uložený text")
        self.assertEqual(tab.editor.area.text(), "BOZP")
        self.assertEqual(tab.editor.note.toPlainText(), "Poznámka")

    def test_workbench_creates_ten_consecutive_requirements(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        sections = self._create_processable_sections(document, version, 10)

        tab = LegalDocumentWorkbenchTab(document_id=document.id, version_id=version.id)
        assert tab.editor is not None

        tab.tree.select_section_id(sections[0].id)
        tab.load_section(sections[0].id)

        for index, section in enumerate(sections):
            tab.editor.regulation_name.setText(f"Požadavek {index + 1}")
            tab.editor.requirement_summary.setPlainText(f"Text požadavku {index + 1}")
            tab.editor.area.setText("BOZP")

            if index < len(sections) - 1:
                requirement_id = tab.save_and_next()
            else:
                requirement_id = tab.save_current()

            self.assertIsNotNone(requirement_id)
            saved = legal_requirement_service.get_by_source_section_id(section.id)
            assert saved is not None
            self.assertEqual(saved.requirement_summary, f"Text požadavku {index + 1}")

        for section in sections:
            saved = legal_requirement_service.get_by_source_section_id(section.id)
            self.assertIsNotNone(saved)
            assert saved is not None
            self.assertTrue(saved.active)

        assert tab.editor is not None
        self.assertEqual(tab.editor.current_section_id(), sections[-1].id)


if __name__ == "__main__":
    unittest.main()
