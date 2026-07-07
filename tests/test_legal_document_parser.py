import importlib
import json
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

    from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
        legal_document_json_import_service,
    )
    from moduly.pravni_pozadavky.parser.legal_document_parser import legal_document_parser
    from moduly.pravni_pozadavky.parser.legal_document_parser_models import (
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalDocumentParserTestCase(unittest.TestCase):
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

        self.sample_path = Path(__file__).resolve().parent / "data" / "sample_zakonik_prace.txt"
        self.sample_text = self.sample_path.read_text(encoding="utf-8")

    def _parse_sample(self):
        return legal_document_parser.parse_text(
            self.sample_text,
            document_type="zakon",
            number="262",
            year=2006,
            title="Zákoník práce",
            short_title="ZP",
        )

    def test_recognizes_paragraph(self) -> None:
        result = self._parse_sample()
        paragraphs = [section for section in result.sections if section.section_type == SECTION_PARAGRAPH]

        self.assertGreaterEqual(len(paragraphs), 2)
        self.assertEqual(paragraphs[0].paragraph, "101")
        self.assertEqual(paragraphs[0].title, "Předmět úpravy")
        self.assertEqual(paragraphs[1].paragraph, "102")

    def test_recognizes_subsection(self) -> None:
        result = self._parse_sample()
        subsections = [
            section for section in result.sections if section.section_type == SECTION_SUBSECTION
        ]

        self.assertGreaterEqual(len(subsections), 3)
        self.assertEqual(subsections[0].section_number, "1")
        self.assertIn("práva a povinnosti", subsections[0].text)
        self.assertEqual(subsections[1].section_number, "2")

    def test_recognizes_letter(self) -> None:
        result = self._parse_sample()
        letters = [section for section in result.sections if section.section_type == SECTION_LETTER]

        self.assertGreaterEqual(len(letters), 3)
        self.assertEqual(letters[0].item_letter, "a")
        self.assertIn("preventivní", letters[0].text)
        self.assertEqual(letters[2].item_letter, "c")

    def test_section_sort_order(self) -> None:
        result = self._parse_sample()

        sort_orders = [section.sort_order for section in result.sections]
        self.assertEqual(sort_orders, list(range(1, len(result.sections) + 1)))

    def test_export_json(self) -> None:
        result = self._parse_sample()

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            temp_path = handle.name

        try:
            legal_document_parser.export_json(temp_path, result)
            exported = json.loads(Path(temp_path).read_text(encoding="utf-8"))
            self.assertIn("document", exported)
            self.assertIn("version", exported)
            self.assertIn("sections", exported)
            self.assertEqual(exported["document"]["title"], "Zákoník práce")
            self.assertGreater(len(exported["sections"]), 0)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_parser_output_is_import_compatible(self) -> None:
        result = self._parse_sample()
        import_result = legal_document_json_import_service.import_data(result.to_dict())

        document = legal_document_service.get_by_id(import_result.document_id)
        version = legal_document_version_service.get_by_id(import_result.version_id)
        sections = legal_section_service.list_by_version(import_result.version_id)

        assert document is not None
        assert version is not None
        self.assertEqual(document.title, "Zákoník práce")
        self.assertEqual(document.number, "262")
        self.assertEqual(version.version_name, "Aktuální znění")
        self.assertEqual(import_result.section_count, len(sections))
        self.assertGreater(len(sections), 0)

        paragraph = next(item for item in sections if item.paragraph == "101")
        self.assertEqual(paragraph.title, "Předmět úpravy")


if __name__ == "__main__":
    unittest.main()
