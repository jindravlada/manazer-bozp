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
        legal_requirement_process_label,
        legal_requirement_provision_label,
        legal_requirement_regulation_label,
        legal_requirement_responsible_label,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_requirement_table import (
        COL_PROCESS,
        COL_RESPONSIBLE,
        COL_SUMMARY,
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

    def test_process_label_uses_title(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Školení BOZP",
            regulation_name="Zákoník práce",
            requirement_summary="Test",
        )

        self.assertEqual(legal_requirement_process_label(requirement), "Školení BOZP")

    def test_process_label_falls_back_to_regulation_name(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Legacy proces",
            requirement_summary="Test",
        )

        self.assertEqual(legal_requirement_process_label(requirement), "Legacy proces")

    def test_responsible_label_combines_person_and_role(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Test",
            requirement_summary="Test",
        )
        requirement.responsible_person_name = "Jan Novák"
        requirement.responsible_role_name = "Vedoucí provozu"
        legal_requirement_service.repository.update(requirement)

        self.assertEqual(
            legal_requirement_responsible_label(requirement),
            "Jan Novák / Vedoucí provozu",
        )

    def test_table_shows_process_and_fulfillment_columns(self) -> None:
        document, version, letter = self._create_hierarchy_with_letter()
        requirement = legal_requirement_service.create_requirement(
            title="Školení BOZP",
            regulation_name="Zákoník práce",
            regulation_number="262/2006 Sb.",
            provision="písm. a",
            area="BOZP",
            legal_document_id=document.id,
            legal_section_id=letter.id,
            source_section_id=letter.id,
            requirement_summary="Zajistit školení zaměstnanců",
        )
        requirement.responsible_person_name = "Jan Novák"
        requirement.responsible_role_name = "Vedoucí provozu"
        legal_requirement_service.repository.update(requirement)

        table = LegalRequirementTable()
        table.load_requirements([requirement])

        self.assertEqual(table.item(0, COL_PROCESS).text(), "Školení BOZP")
        self.assertEqual(table.item(0, COL_SUMMARY).text(), "Zajistit školení zaměstnanců")
        self.assertEqual(table.item(0, COL_RESPONSIBLE).text(), "Jan Novák / Vedoucí provozu")

    def test_table_shows_imported_process_title(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Systém řízení BOZP",
            regulation_name="Zákoník práce",
            requirement_summary="Zajistit systém řízení BOZP",
        )

        table = LegalRequirementTable()
        table.load_requirements([requirement])

        self.assertEqual(table.item(0, COL_PROCESS).text(), "Systém řízení BOZP")
        self.assertEqual(table.item(0, COL_SUMMARY).text(), "Zajistit systém řízení BOZP")

    def test_refresh_sorts_by_process_name(self) -> None:
        legal_requirement_service.create_requirement(
            title="Zápis do dokumentace",
            requirement_summary="A",
        )
        legal_requirement_service.create_requirement(
            title="Školení BOZP",
            requirement_summary="B",
        )
        legal_requirement_service.create_requirement(
            title="Hodnocení rizik",
            requirement_summary="C",
        )

        tab = PravniPozadavkyRequirementsTab()
        tab.refresh()

        process_names = [
            tab.table.item(row, COL_PROCESS).text()
            for row in range(tab.table.rowCount())
        ]
        self.assertEqual(process_names, ["Hodnocení rizik", "Školení BOZP", "Zápis do dokumentace"])

    def test_text_filter_searches_process_and_fulfillment(self) -> None:
        legal_requirement_service.create_requirement(
            title="Školení BOZP",
            requirement_summary="Zajistit školení zaměstnanců",
        )
        legal_requirement_service.create_requirement(
            title="Hodnocení rizik",
            requirement_summary="Provést analýzu pracoviště",
        )

        tab = PravniPozadavkyRequirementsTab()
        tab.refresh()

        tab.text_filter.search_edit.setText("školení")
        tab.text_filter.apply_filter()
        visible_processes = [
            tab.table.item(row, COL_PROCESS).text()
            for row in range(tab.table.rowCount())
            if not tab.table.isRowHidden(row)
        ]
        self.assertEqual(visible_processes, ["Školení BOZP"])

        tab.text_filter.search_edit.setText("analýzu")
        tab.text_filter.apply_filter()
        visible_processes = [
            tab.table.item(row, COL_PROCESS).text()
            for row in range(tab.table.rowCount())
            if not tab.table.isRowHidden(row)
        ]
        self.assertEqual(visible_processes, ["Hodnocení rizik"])


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
