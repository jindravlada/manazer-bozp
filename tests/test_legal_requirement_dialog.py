import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

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
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_creation_service import (
        legal_requirement_creation_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_requirement_dialog import LegalRequirementDialog


class LegalRequirementDialogFromSectionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
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

    def _create_document(
        self,
        *,
        title: str = "Zákoník práce",
        number: str = "262/2006 Sb.",
        year: int = 2006,
        short_title: str = "ZP",
    ):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title=title,
            number=number,
            year=year,
            short_title=short_title,
        )

    def _create_subsection_101_odst_2(self, document=None):
        document = document or self._create_document()
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
            section_number="2",
            text="Text odstavce 2",
            sort_order=2,
        )
        return document, subsection

    def _form_labels(self, dialog: LegalRequirementDialog) -> list[str]:
        labels = []
        for widget in dialog.findChildren(QLabel):
            text = widget.text().strip()
            if text.endswith(":"):
                labels.append(text)
        return labels

    def test_dialog_prefills_fields_when_created_from_section(self) -> None:
        _document, subsection = self._create_subsection_101_odst_2()
        draft = legal_requirement_creation_service.create_from_section(subsection.id)

        dialog = LegalRequirementDialog(draft=draft)

        self.assertEqual(dialog.regulation_name.currentText(), "Zákoník práce")
        self.assertEqual(dialog.regulation_number.text(), "262/2006 Sb.")
        self.assertEqual(dialog.provision.text(), "§ 101 odst. 2")
        self.assertEqual(dialog.legal_section.currentText(), "§ 101 odst. 2")
        self.assertEqual(dialog.sources_widget.get_section_ids(), [subsection.id])
        self.assertNotIn("Právní předpis:", self._form_labels(dialog))
        self.assertNotIn("Oblast:", self._form_labels(dialog))
        self.assertEqual(dialog.get_data()["legal_document_id"], _document.id)

    def test_selecting_name_fills_regulation_number(self) -> None:
        self._create_document()
        dialog = LegalRequirementDialog()
        dialog.regulation_number.clear()

        dialog.regulation_name.apply_search_text("Zákoník práce")

        self.assertEqual(dialog.regulation_name.currentText(), "Zákoník práce")
        self.assertEqual(dialog.regulation_number.text(), "262/2006 Sb.")

    def test_selecting_number_fills_regulation_name(self) -> None:
        self._create_document()
        dialog = LegalRequirementDialog()
        dialog.regulation_name.setCurrentText("")
        dialog.regulation_number.setText("262/2006 Sb.")

        self.assertEqual(dialog.regulation_name.currentText(), "Zákoník práce")
        self.assertEqual(dialog.regulation_number.text(), "262/2006 Sb.")

    def test_selecting_short_title_fills_name_and_number(self) -> None:
        self._create_document()
        dialog = LegalRequirementDialog()
        dialog.regulation_name.setCurrentText("")
        dialog.regulation_number.clear()

        dialog.regulation_name.apply_search_text("ZP")

        self.assertEqual(dialog.regulation_name.currentText(), "Zákoník práce")
        self.assertEqual(dialog.regulation_number.text(), "262/2006 Sb.")

    def test_changing_document_clears_selected_section_but_keeps_sources(self) -> None:
        first_document, subsection = self._create_subsection_101_odst_2()
        second_document = self._create_document(
            title="Nařízení vlády",
            number="390/2021",
            year=2021,
            short_title="NV",
        )
        second_version = legal_document_version_service.create(
            legal_document_id=second_document.id,
            version_name="Verze 2021",
        )
        second_section = legal_section_service.create(
            legal_document_id=second_document.id,
            legal_document_version_id=second_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="5",
            title="Test",
            sort_order=1,
        )

        draft = legal_requirement_creation_service.create_from_section(subsection.id)
        dialog = LegalRequirementDialog(draft=draft)
        self.assertEqual(dialog.legal_section.currentData(), subsection.id)
        self.assertEqual(dialog.sources_widget.get_section_ids(), [subsection.id])

        dialog.regulation_name.apply_search_text("Nařízení vlády")

        self.assertIsNone(dialog.legal_section.currentData())
        self.assertEqual(dialog.sources_widget.get_section_ids(), [subsection.id])
        self.assertEqual(dialog.get_data()["legal_document_id"], second_document.id)
        section_ids = [
            dialog.legal_section.itemData(index)
            for index in range(dialog.legal_section.count())
        ]
        self.assertIn(second_section.id, section_ids)
        self.assertNotIn(subsection.id, section_ids)
        self.assertNotIn(first_document.id, [dialog.get_data()["legal_document_id"]])

    def test_dialog_shows_pravni_podklady_label(self) -> None:
        dialog = LegalRequirementDialog()
        labels = self._form_labels(dialog)
        self.assertIn("Právní podklady:", labels)
        self.assertNotIn("Vychází z:", labels)

    def test_dialog_shows_zpusob_plneni_label(self) -> None:
        dialog = LegalRequirementDialog()
        labels = [label.text() for label in dialog.findChildren(QLabel)]

        self.assertIn("Způsob plnění:", labels)
        self.assertNotIn("Stručný požadavek:", labels)
        self.assertEqual(dialog.requirement_summary.toolTip(), "")

    def test_dialog_uses_process_terminology_labels(self) -> None:
        dialog = LegalRequirementDialog()
        labels = self._form_labels(dialog)

        self.assertIn("Řídicí proces:", labels)
        self.assertIn("Hlavní právní předpis:", labels)
        self.assertIn("Hlavní právní podklad:", labels)
        self.assertNotIn("Název předpisu:", labels)
        self.assertNotIn("Číslo předpisu:", labels)
        self.assertNotIn("Ustanovení:", labels)
        self.assertEqual(dialog.tabs.tabText(0), "Řídicí proces")

    def test_edit_dialog_shows_process_title(self) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service

        _document, subsection = self._create_subsection_101_odst_2()
        draft = legal_requirement_creation_service.create_from_section(subsection.id)
        requirement = legal_requirement_service.create_requirement(
            title="Řízení systému BOZP",
            regulation_name=draft.regulation_name,
            regulation_number=draft.regulation_number,
            provision=draft.provision,
            legal_document_id=draft.legal_document_id,
            legal_section_id=draft.legal_section_id,
            source_section_id=draft.source_section_id,
            source_section_ids=[draft.source_section_id],
        )

        dialog = LegalRequirementDialog(requirement=requirement)

        self.assertEqual(dialog.windowTitle(), "Upravit řídicí proces")
        self.assertEqual(dialog.process_title.text(), "Řízení systému BOZP")


if __name__ == "__main__":
    unittest.main()
