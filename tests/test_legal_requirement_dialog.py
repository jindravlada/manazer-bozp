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

    def _create_subsection_101_odst_2(self):
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
            section_number="2",
            text="Text odstavce 2",
            sort_order=2,
        )
        return subsection

    def _form_labels(self, dialog: LegalRequirementDialog) -> list[str]:
        labels = []
        for widget in dialog.findChildren(QLabel):
            text = widget.text().strip()
            if text.endswith(":"):
                labels.append(text)
        return labels

    def test_dialog_prefills_fields_when_created_from_section(self) -> None:
        subsection = self._create_subsection_101_odst_2()
        draft = legal_requirement_creation_service.create_from_section(subsection.id)

        dialog = LegalRequirementDialog(draft=draft)

        self.assertEqual(dialog.regulation_name.text(), "Zákoník práce")
        self.assertEqual(dialog.provision.text(), "§ 101 odst. 2")
        self.assertEqual(dialog.legal_section.currentText(), "§ 101 odst. 2")
        self.assertEqual(dialog.source_section_display.text(), "ZP – § 101 odst. 2")
        self.assertNotIn("Oblast:", self._form_labels(dialog))
        self.assertEqual(dialog.get_data()["area"], "")


if __name__ == "__main__":
    unittest.main()
