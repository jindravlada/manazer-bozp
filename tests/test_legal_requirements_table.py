import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import QApplication

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
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
        legal_requirement_provision_label,
        legal_requirement_regulation_label,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_requirement_table import (
        COL_AREA,
        COL_PROVISION,
        COL_REGULATION,
        LegalRequirementTable,
    )
    from moduly.pravni_pozadavky.ui.pravni_pozadavky_page import PravniPozadavkyPage
    from moduly.pravni_pozadavky.ui.pravni_pozadavky_requirements_tab import (
        PravniPozadavkyRequirementsTab,
    )


class LegalRequirementTableDisplayTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for requirement in legal_requirement_service.get_all():
            requirement.active = False
            legal_requirement_service.repository.update(requirement)

    def _create_hierarchy_with_letter(self):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="Předmět",
            sort_order=1,
        )
        subsection = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="1",
            sort_order=2,
        )
        letter = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=subsection.id,
            item_letter="a",
            sort_order=3,
        )
        return document, version, letter

    def test_regulation_label_prefers_number(self) -> None:
        document, version, letter = self._create_hierarchy_with_letter()
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Zákoník práce",
            regulation_number="262/2006 Sb.",
            legal_document_id=document.id,
            legal_section_id=letter.id,
            source_section_id=letter.id,
            requirement_summary="Test",
        )

        self.assertEqual(legal_requirement_regulation_label(requirement), "262/2006 Sb.")

    def test_provision_label_builds_full_hierarchy(self) -> None:
        document, version, letter = self._create_hierarchy_with_letter()
        sections = legal_section_service.list_by_version(version.id)
        sections_by_id = {section.id: section for section in sections}
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Zákoník práce",
            regulation_number="262/2006 Sb.",
            provision="písm. a",
            legal_document_id=document.id,
            legal_section_id=letter.id,
            source_section_id=letter.id,
            requirement_summary="Test",
        )

        label = legal_requirement_provision_label(
            requirement,
            section=sections_by_id[letter.id],
            sections_by_id=sections_by_id,
        )
        self.assertEqual(label, "§ 101 odst. 1 písm. a)")

    def test_table_hides_area_column_and_shows_formatted_values(self) -> None:
        document, version, letter = self._create_hierarchy_with_letter()
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Zákoník práce",
            regulation_number="262/2006 Sb.",
            provision="písm. a",
            area="BOZP",
            legal_document_id=document.id,
            legal_section_id=letter.id,
            source_section_id=letter.id,
            requirement_summary="Test požadavku",
        )

        table = LegalRequirementTable()
        table.load_requirements([requirement])

        self.assertTrue(table.isColumnHidden(COL_AREA))
        self.assertEqual(table.item(0, COL_REGULATION).text(), "262/2006 Sb.")
        self.assertEqual(table.item(0, COL_PROVISION).text(), "§ 101 odst. 1 písm. a)")


class PravniPozadavkyRequirementsTabSelectionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for requirement in legal_requirement_service.get_all():
            requirement.active = False
            legal_requirement_service.repository.update(requirement)

    def _create_requirement(self):
        return legal_requirement_service.create_requirement(
            regulation_name="Zákoník práce",
            regulation_number="262/2006 Sb.",
            provision="§ 101",
            requirement_summary="Test",
        )

    def test_refresh_clears_selection(self) -> None:
        self._create_requirement()
        tab = PravniPozadavkyRequirementsTab()
        tab.table.selectRow(0)

        tab.refresh()

        self.assertEqual(len(tab.table.selectionModel().selectedRows()), 0)
        self.assertFalse(tab.table.selectionModel().currentIndex().isValid())

    def test_hide_event_clears_selection(self) -> None:
        self._create_requirement()
        tab = PravniPozadavkyRequirementsTab()
        tab.table.selectRow(0)

        tab.hideEvent(QHideEvent())

        self.assertEqual(len(tab.table.selectionModel().selectedRows()), 0)

    def test_show_event_clears_selection(self) -> None:
        self._create_requirement()
        tab = PravniPozadavkyRequirementsTab()
        tab.table.selectRow(0)

        tab.showEvent(QShowEvent())

        self.assertEqual(len(tab.table.selectionModel().selectedRows()), 0)

    def test_switching_tabs_clears_selection(self) -> None:
        requirement = self._create_requirement()
        page = PravniPozadavkyPage()
        page.requirements_tab.table.selectRow(0)

        page.tabs.setCurrentWidget(page.documents_tab)
        page.tabs.setCurrentWidget(page.requirements_tab)

        self.assertEqual(len(page.requirements_tab.table.selectionModel().selectedRows()), 0)

    def test_show_created_requirement_selects_new_record(self) -> None:
        requirement = self._create_requirement()
        tab = PravniPozadavkyRequirementsTab()

        tab.show_created_requirement(requirement.id)

        self.assertEqual(len(tab.table.selectionModel().selectedRows()), 1)
        selected_row = tab.table.selectionModel().selectedRows()[0].row()
        self.assertEqual(tab.table.item(selected_row, 0).text(), str(requirement.id))


if __name__ == "__main__":
    unittest.main()
