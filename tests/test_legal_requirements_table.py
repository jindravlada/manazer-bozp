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
        COL_CODE,
        COL_LAST_CHECK,
        COL_NEXT_CHECK,
        COL_PERIODICITY,
        COL_PROCESS,
        COL_RESPONSIBLE,
        COL_STATUS,
        COL_SUMMARY,
        PROCESS_NAME_PREVIEW_LENGTH,
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
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        with get_session() as session:
            session.execute(delete(LegalRequirement))
            session.commit()

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

    def test_table_truncates_long_fulfillment_text_and_shows_tooltip(self) -> None:
        from core.widgets.text_preview import DEFAULT_TEXT_PREVIEW_LENGTH, TEXT_PREVIEW_SUFFIX

        full_text = (
            "Zaměstnavatel stanoví a udržuje systém řízení bezpečnosti a ochrany zdraví při práci "
            "v souladu s požadavky zákona a prováděcích předpisů pro všechna pracoviště organizace."
        )
        requirement = legal_requirement_service.create_requirement(
            title="Systém řízení BOZP",
            regulation_name="Zákoník práce",
            requirement_summary=full_text,
        )

        table = LegalRequirementTable()
        table.load_requirements([requirement])

        summary_item = table.item(0, COL_SUMMARY)
        assert summary_item is not None
        self.assertEqual(
            summary_item.text(),
            f"{full_text[:DEFAULT_TEXT_PREVIEW_LENGTH]}{TEXT_PREVIEW_SUFFIX}",
        )
        self.assertIn("Zaměstnavatel stanoví", summary_item.toolTip())
        self.assertIn("prováděcích předpisů", summary_item.toolTip())

    def test_table_truncates_long_process_title_and_shows_tooltip(self) -> None:
        from core.widgets.text_preview import TEXT_PREVIEW_SUFFIX

        full_title = (
            "Řízení vyhrazených technických zařízení v energetických a průmyslových provozech"
        )
        requirement = legal_requirement_service.create_requirement(
            title=full_title,
            requirement_summary="Test",
        )

        table = LegalRequirementTable()
        table.load_requirements([requirement])

        process_item = table.item(0, COL_PROCESS)
        assert process_item is not None
        self.assertEqual(
            process_item.text(),
            f"{full_title[:PROCESS_NAME_PREVIEW_LENGTH]}{TEXT_PREVIEW_SUFFIX}",
        )
        self.assertIn("Řízení vyhrazených technických zařízení", process_item.toolTip())
        self.assertIn("průmyslových provozech", process_item.toolTip())

    def test_table_column_widths_are_balanced(self) -> None:
        from PySide6.QtWidgets import QHeaderView

        from core.widgets.table_utils import configure_table_columns

        table = LegalRequirementTable()
        configure_table_columns(table, "legal_requirements")
        header = table.horizontalHeader()

        fixed_widths = {
            COL_CODE: 72,
            COL_PROCESS: 200,
            COL_RESPONSIBLE: 200,
            COL_STATUS: 120,
            COL_NEXT_CHECK: 110,
            COL_LAST_CHECK: 110,
            COL_PERIODICITY: 120,
        }
        for column, width in fixed_widths.items():
            self.assertEqual(table.columnWidth(column), width)
            self.assertEqual(header.sectionResizeMode(column), QHeaderView.ResizeMode.Fixed)

        self.assertEqual(header.sectionResizeMode(COL_SUMMARY), QHeaderView.ResizeMode.Stretch)

    def test_summary_column_stretches_with_table_width(self) -> None:
        from core.widgets.table_utils import configure_table_columns

        table = LegalRequirementTable()
        configure_table_columns(table, "legal_requirements")
        table.show()
        self._app.processEvents()

        table.resize(1600, 400)
        self._app.processEvents()
        summary_width_wide = table.columnWidth(COL_SUMMARY)

        table.resize(1200, 400)
        self._app.processEvents()
        summary_width_narrow = table.columnWidth(COL_SUMMARY)

        self.assertGreater(summary_width_wide, summary_width_narrow)
        self.assertEqual(table.columnWidth(COL_PROCESS), 200)
        self.assertEqual(table.columnWidth(COL_PERIODICITY), 120)

    def test_refresh_sorts_by_process_code(self) -> None:
        from moduly.pravni_pozadavky.constants import process_code_sort_key
        from moduly.pravni_pozadavky.ui.legal_requirement_table import COL_CODE

        third = legal_requirement_service.create_requirement(
            title="Zápis do dokumentace",
            requirement_summary="A",
        )
        first = legal_requirement_service.create_requirement(
            title="Školení BOZP",
            requirement_summary="B",
        )
        second = legal_requirement_service.create_requirement(
            title="Hodnocení rizik",
            requirement_summary="C",
        )

        tab = PravniPozadavkyRequirementsTab()
        tab.refresh()

        process_codes = [
            tab.table.item(row, COL_CODE).text()
            for row in range(tab.table.rowCount())
        ]
        self.assertEqual(process_codes, ["P-001", "P-002", "P-003"])

    def test_level_filter_defaults_to_root_processes(self) -> None:
        from moduly.pravni_pozadavky.constants import DEFAULT_PROCESS_LEVEL_FILTER
        from moduly.pravni_pozadavky.ui.legal_requirement_table import COL_CODE

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )

        tab = PravniPozadavkyRequirementsTab()

        self.assertEqual(tab.level_filter.currentText(), DEFAULT_PROCESS_LEVEL_FILTER)
        tab.refresh()

        process_codes = [
            tab.table.item(row, COL_CODE).text()
            for row in range(tab.table.rowCount())
        ]
        self.assertEqual(process_codes, ["P-015"])

    def test_level_filter_all_shows_roots_and_children(self) -> None:
        from moduly.pravni_pozadavky.constants import (
            FILTER_PROCESS_LEVEL_ALL,
            process_code_sort_key,
        )
        from moduly.pravni_pozadavky.ui.legal_requirement_table import COL_CODE

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )

        tab = PravniPozadavkyRequirementsTab()
        tab.level_filter.setCurrentText(FILTER_PROCESS_LEVEL_ALL)
        tab.refresh()

        process_codes = [
            tab.table.item(row, COL_CODE).text()
            for row in range(tab.table.rowCount())
        ]
        self.assertEqual(
            process_codes,
            [
                item.process_code
                for item in sorted([root, child], key=process_code_sort_key)
            ],
        )

    def test_level_filter_children_shows_only_child_processes(self) -> None:
        from moduly.pravni_pozadavky.constants import FILTER_PROCESS_LEVEL_CHILDREN
        from moduly.pravni_pozadavky.ui.legal_requirement_table import COL_CODE

        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )

        tab = PravniPozadavkyRequirementsTab()
        tab.level_filter.setCurrentText(FILTER_PROCESS_LEVEL_CHILDREN)
        tab.refresh()

        process_codes = [
            tab.table.item(row, COL_CODE).text()
            for row in range(tab.table.rowCount())
        ]
        self.assertEqual(process_codes, [child.process_code])

    def test_level_filter_all_sorts_hierarchical_process_codes(self) -> None:
        from moduly.pravni_pozadavky.constants import FILTER_PROCESS_LEVEL_ALL
        from moduly.pravni_pozadavky.ui.legal_requirement_table import COL_CODE

        legal_requirement_service.create_requirement(
            title="Kořen B",
            process_code="P-016",
        )
        root_a = legal_requirement_service.create_requirement(
            title="Kořen A",
            process_code="P-015",
        )
        legal_requirement_service.create_requirement(
            title="Druhé dítě",
            parent_requirement_id=root_a.id,
        )
        legal_requirement_service.create_requirement(
            title="První dítě",
            parent_requirement_id=root_a.id,
        )

        tab = PravniPozadavkyRequirementsTab()
        tab.level_filter.setCurrentText(FILTER_PROCESS_LEVEL_ALL)
        tab.refresh()

        process_codes = [
            tab.table.item(row, COL_CODE).text()
            for row in range(tab.table.rowCount())
        ]
        self.assertEqual(
            process_codes,
            ["P-015", "P-015.1", "P-015.2", "P-016"],
        )

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
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        with get_session() as session:
            session.execute(delete(LegalRequirement))
            session.commit()

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


class PravniPozadavkyRequirementsTabOwnerFilterTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        with get_session() as session:
            session.execute(delete(LegalRequirement))
            session.commit()

    def test_owner_filter_limits_processes_by_role(self) -> None:
        from core.widgets.search_combo_box import SearchComboBox
        from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service
        from moduly.pravni_pozadavky.constants import FILTER_OWNER_VSE

        roles = {
            role.name: role
            for role in responsibility_role_service.get_all(include_inactive=False)
        }
        owner_a = roles["Vedoucí provozu"]
        owner_b = roles["OZO BOZP"]

        legal_requirement_service.create_requirement(
            title="Proces A",
            requirement_summary="A",
            responsible_role_id=owner_a.id,
        )
        legal_requirement_service.create_requirement(
            title="Proces B",
            requirement_summary="B",
            responsible_role_id=owner_b.id,
        )

        tab = PravniPozadavkyRequirementsTab()
        self.assertFalse(hasattr(tab, "area_filter"))
        self.assertIsInstance(tab.owner_filter, SearchComboBox)
        self.assertTrue(tab.owner_filter.isEditable())
        self.assertEqual(tab.owner_filter.itemText(0), FILTER_OWNER_VSE)
        self.assertEqual(tab.table.rowCount(), 2)

        tab.owner_filter.set_value(owner_a.name)
        tab.refresh()
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(tab.table.item(0, COL_PROCESS).text(), "Proces A")


if __name__ == "__main__":
    unittest.main()
