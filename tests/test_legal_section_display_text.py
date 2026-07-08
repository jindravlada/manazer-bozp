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
        DOCUMENT_TYPE_VYHLASKA,
        SECTION_ATTACHMENT,
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_display_text_service import (
        legal_section_display_text_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalSectionDisplayTextServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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

    def _create_document_432(self):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška č. 432/2003 Sb.",
            number="432",
            year=2003,
            short_title="V432",
        )

    def _create_version(self, document_id: int):
        return legal_document_version_service.create(
            legal_document_id=document_id,
            version_name="Aktuální znění",
        )

    def test_compose_paragraph_text_from_subsections_like_432_section_2(self) -> None:
        document = self._create_document_432()
        version = self._create_version(document.id)
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="2",
            title="(K § 37 zákona)",
            sort_order=1,
        )
        texts = [
            "Zařazení práce do kategorie vyjadřuje souhrnné hodnocení.",
            "Při zařazování prací do kategorií se stanoví kategorie rozhodujících faktorů.",
            "Při zařazování prací do kategorií se bere v úvahu vzájemné ovlivňování.",
        ]
        for index, text in enumerate(texts, start=1):
            legal_section_service.create(
                legal_document_id=document.id,
                legal_document_version_id=version.id,
                section_type=SECTION_SUBSECTION,
                parent_section_id=paragraph.id,
                section_number=str(index),
                text=text,
                sort_order=index,
            )

        composed = legal_section_display_text_service.compose(paragraph.id)

        self.assertTrue(composed.startswith("§ 2\n\n"))
        self.assertIn("(1) Zařazení práce do kategorie vyjadřuje souhrnné hodnocení.", composed)
        self.assertIn(
            "(2) Při zařazování prací do kategorií se stanoví kategorie rozhodujících faktorů.",
            composed,
        )
        self.assertIn(
            "(3) Při zařazování prací do kategorií se bere v úvahu vzájemné ovlivňování.",
            composed,
        )
        self.assertEqual(composed.count("\n\n"), 3)

    def test_compose_attachment_text_from_own_node(self) -> None:
        document = self._create_document_432()
        version = self._create_version(document.id)
        attachment = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_ATTACHMENT,
            section_number="1",
            title="Příloha č. 1 k vyhlášce č. 432/2003 Sb.",
            text="Kritéria kategorizace prací\n1. PRACH",
            sort_order=1,
        )

        composed = legal_section_display_text_service.compose(attachment.id)

        self.assertEqual(composed, "Kritéria kategorizace prací\n1. PRACH")

    def test_compose_returns_empty_for_section_without_text(self) -> None:
        document = self._create_document_432()
        version = self._create_version(document.id)
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="201",
            sort_order=1,
        )

        composed = legal_section_display_text_service.compose(paragraph.id)

        self.assertEqual(composed, "")

    def test_compose_paragraph_includes_letters_and_numbered_points_like_180_section_2(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška č. 180/2015 Sb.",
            number="180",
            year=2015,
            short_title="V180",
        )
        version = self._create_version(document.id)
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="2",
            sort_order=1,
        )
        odstavec = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="1",
            text="Těhotným zaměstnankyním jsou zakázány práce",
            sort_order=2,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=odstavec.id,
            item_letter="a",
            text="rizikové, s výjimkou\n1. prací první\n2. prací druhé",
            sort_order=3,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=odstavec.id,
            item_letter="b",
            text="vyžadující používání izolačních dýchacích přístrojů",
            sort_order=4,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="2",
            text="Těhotným zaměstnankyním jsou dále zakázány práce",
            sort_order=5,
        )

        composed = legal_section_display_text_service.compose(paragraph.id)

        self.assertTrue(composed.startswith("§ 2\n\n"))
        self.assertIn("(1) Těhotným zaměstnankyním jsou zakázány práce", composed)
        self.assertIn("    a) rizikové, s výjimkou", composed)
        self.assertIn("        1. prací první", composed)
        self.assertIn("        2. prací druhé", composed)
        self.assertIn("    b) vyžadující používání izolačních dýchacích přístrojů", composed)
        self.assertIn("(2) Těhotným zaměstnankyním jsou dále zakázány práce", composed)


if __name__ == "__main__":
    unittest.main()
