"""Fáze 98a – sjednocené označení ustanovení v panelu Znění právního podkladu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        DOCUMENT_TYPE_VYHLASKA,
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
        legal_section_provision_label,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_display_text_service import (
        legal_section_display_text_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_requirement_dialog import LegalRequirementDialog


class LegalRequirementProvisionLabelPhase98aTestCase(unittest.TestCase):
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

        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška č. 180/2015 Sb.",
            number="180",
            year=2015,
            short_title="V180",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
        )
        self._paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="4",
            title="Zaměstnankyním-matkám jsou zakázány práce uvedené",
            sort_order=1,
        )
        self._subsection = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=self._paragraph.id,
            section_number="1",
            text="Text prvního odstavce.",
            sort_order=2,
        )
        self._letter = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=self._subsection.id,
            item_letter="c",
            text="Text písmene c).",
            sort_order=3,
        )
        self._sections_by_id = legal_section_service.build_sections_map(
            [self._paragraph, self._subsection, self._letter],
        )

    def test_legal_section_provision_label_formats_hierarchy(self) -> None:
        self.assertEqual(
            legal_section_provision_label(self._paragraph, sections_by_id=self._sections_by_id),
            "§ 4",
        )
        self.assertEqual(
            legal_section_provision_label(self._subsection, sections_by_id=self._sections_by_id),
            "§ 4 odst. 1",
        )
        self.assertEqual(
            legal_section_provision_label(self._letter, sections_by_id=self._sections_by_id),
            "§ 4 odst. 1 písm. c)",
        )

    def _dialog_header_for(self, section_id: int) -> str:
        dialog = LegalRequirementDialog()
        dialog.sources_widget.load_section_ids([section_id])
        return dialog.provision_text_header.text()

    def _dialog_body_for(self, section_id: int) -> str:
        dialog = LegalRequirementDialog()
        dialog.sources_widget.load_section_ids([section_id])
        return dialog.provision_text_view.toPlainText()

    def test_dialog_header_uses_shared_formatter_for_paragraph(self) -> None:
        self.assertEqual(self._dialog_header_for(self._paragraph.id), "180/2015 Sb.\n§ 4")

    def test_dialog_header_uses_shared_formatter_for_subsection(self) -> None:
        self.assertEqual(
            self._dialog_header_for(self._subsection.id),
            "180/2015 Sb.\n§ 4 odst. 1",
        )

    def test_dialog_header_uses_shared_formatter_for_letter(self) -> None:
        self.assertEqual(
            self._dialog_header_for(self._letter.id),
            "180/2015 Sb.\n§ 4 odst. 1 písm. c)",
        )

    def test_dialog_body_does_not_repeat_provision_label(self) -> None:
        paragraph_body = self._dialog_body_for(self._paragraph.id)
        self.assertFalse(paragraph_body.startswith("§ 4"))
        self.assertIn("Zaměstnankyním-matkám jsou zakázány práce uvedené", paragraph_body)
        self.assertIn("(1) Text prvního odstavce.", paragraph_body)

        subsection_body = self._dialog_body_for(self._subsection.id)
        self.assertIn("Zaměstnankyním-matkám jsou zakázány práce uvedené", subsection_body)
        self.assertIn("Text prvního odstavce.", subsection_body)
        self.assertNotIn("Text písmene c).", subsection_body)
        self.assertFalse(subsection_body.startswith("§ 4"))

        letter_body = self._dialog_body_for(self._letter.id)
        self.assertIn("Zaměstnankyním-matkám jsou zakázány práce uvedené", letter_body)
        self.assertIn("Text prvního odstavce.", letter_body)
        self.assertIn("Text písmene c).", letter_body)
        self.assertFalse(letter_body.startswith("§ 4"))

    def test_compose_without_root_label_keeps_valid_text_format(self) -> None:
        composed_with_label = legal_section_display_text_service.compose(self._paragraph.id)
        composed_without_label = legal_section_display_text_service.compose(
            self._paragraph.id,
            include_root_provision_label=False,
        )

        self.assertTrue(composed_with_label.startswith("§ 4\n\n"))
        self.assertFalse(composed_without_label.startswith("§ 4"))
        self.assertIn("Zaměstnankyním-matkám jsou zakázány práce uvedené", composed_without_label)


if __name__ == "__main__":
    unittest.main()
