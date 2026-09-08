import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
        CHANGE_NOVELIZATION,
        CHANGE_SECTION_ADDED,
        CHANGE_SECTION_MODIFIED,
        CHANGE_SECTION_REMOVED,
        SECTION_PARAGRAPH,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_section_service import (
        legal_change_section_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
        SectionStructureCompareResult,
        SectionStructureEntry,
    )
    from moduly.pravni_pozadavky.ui.legal_change_detail_dialog import LegalChangeDetailDialog


class LegalChangeSectionServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalChangeSection))
            session.execute(delete(LegalChange))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

    def _create_change(self):
        document = legal_document_service.create(
            document_type="zakon",
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
        )
        run = legal_check_run_service.create(
            title="Kontrola",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
        )
        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_check_run_id=run.id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
        )
        return change

    def test_add_sections_to_change_maps_compare_result(self) -> None:
        change = self._create_change()
        compare_result = SectionStructureCompareResult(
            new=[
                SectionStructureEntry("§:104", "§104", "fp1"),
            ],
            removed=[
                SectionStructureEntry("priloha:1", "Příloha č.1", "fp2"),
            ],
            changed=[
                SectionStructureEntry("§:103", "§103", "fp3"),
                SectionStructureEntry("§:103/odst:2", "§103 odst.2", "fp4"),
            ],
        )

        saved = legal_change_section_service.add_sections_to_change(change.id, compare_result)
        listed = legal_change_section_service.list_sections_for_change(change.id)

        self.assertEqual(len(saved), 4)
        self.assertEqual(len(listed), 4)
        self.assertEqual(
            {item.change_type for item in listed},
            {CHANGE_SECTION_ADDED, CHANGE_SECTION_REMOVED, CHANGE_SECTION_MODIFIED},
        )
        self.assertEqual(
            sorted(item.section_label for item in listed if item.change_type == CHANGE_SECTION_ADDED),
            ["§104"],
        )
        self.assertEqual(
            sorted(item.section_label for item in listed if item.change_type == CHANGE_SECTION_REMOVED),
            ["Příloha č.1"],
        )
        self.assertEqual(
            sorted(item.section_label for item in listed if item.change_type == CHANGE_SECTION_MODIFIED),
            ["§103", "§103 odst.2"],
        )

    def test_add_sections_stores_old_and_new_text(self) -> None:
        change = self._create_change()
        compare_result = SectionStructureCompareResult(
            new=[
                SectionStructureEntry(
                    "§:7a",
                    "§7a",
                    "fp-new",
                    text="nové znění",
                    old_text=None,
                    new_text="nové znění",
                ),
            ],
            removed=[
                SectionStructureEntry(
                    "§:12a",
                    "§12a",
                    "fp-old",
                    text="původní znění",
                    old_text="původní znění",
                    new_text=None,
                ),
            ],
            changed=[
                SectionStructureEntry(
                    "§:5/odst:2",
                    "§5 odst.2",
                    "fp-ch",
                    text="nový text",
                    old_text="starý text",
                    new_text="nový text",
                ),
            ],
        )

        listed = legal_change_section_service.add_sections_to_change(change.id, compare_result)
        by_type = {item.change_type: item for item in listed}
        self.assertIsNone(by_type[CHANGE_SECTION_ADDED].old_text)
        self.assertEqual(by_type[CHANGE_SECTION_ADDED].new_text, "nové znění")
        self.assertEqual(by_type[CHANGE_SECTION_REMOVED].old_text, "původní znění")
        self.assertIsNone(by_type[CHANGE_SECTION_REMOVED].new_text)
        self.assertEqual(by_type[CHANGE_SECTION_MODIFIED].old_text, "starý text")
        self.assertEqual(by_type[CHANGE_SECTION_MODIFIED].new_text, "nový text")

    def test_add_sections_to_change_with_empty_result(self) -> None:
        change = self._create_change()
        saved = legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(),
        )
        self.assertEqual(saved, [])
        self.assertEqual(legal_change_section_service.list_sections_for_change(change.id), [])

    def test_detail_dialog_shows_original_and_new_section_text(self) -> None:
        document = legal_document_service.create(
            document_type="zakon",
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
        )
        old_version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
        )
        new_version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Nově zjištěné znění – e-Sbírka 1",
            pending_adoption=True,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="5",
            title="§ 5",
            text="Původní text § 5",
            sort_order=1,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=new_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="5",
            title="§ 5",
            text="Nový text § 5",
            sort_order=1,
        )
        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            new_legal_document_version_id=new_version.id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
        )

        dialog = LegalChangeDetailDialog(change=change)
        self.assertEqual(dialog.sections_table.columnCount(), 2)
        self.assertEqual(
            [
                dialog.sections_table.horizontalHeaderItem(index).text()
                for index in range(dialog.sections_table.columnCount())
            ],
            ["Typ změny", "Ustanovení"],
        )
        self.assertEqual(dialog.sections_table.item(0, 0).text(), "Změněno")
        self.assertIn("5", dialog.sections_table.item(0, 1).text())
        self.assertEqual(dialog.old_text_edit.toPlainText(), "Původní text § 5")
        self.assertEqual(dialog.new_text_edit.toPlainText(), "Nový text § 5")
        self.assertTrue(dialog.old_text_edit.isReadOnly())
        self.assertTrue(dialog.new_text_edit.isReadOnly())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
