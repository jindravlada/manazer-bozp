import importlib
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

    from moduly.pravni_pozadavky.import_export.legal_document_txt_import_service import (
        legal_document_txt_import_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalDocumentTxtImportTestCase(unittest.TestCase):
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

    def _import_sample(self):
        return legal_document_txt_import_service.import_from_txt(
            self.sample_path,
            document_type="zakon",
            number="262",
            year=2006,
            title="Zákoník práce",
            short_title="ZP",
        )

    def test_import_txt_creates_document(self) -> None:
        result = self._import_sample()

        document = legal_document_service.get_by_id(result.document_id)
        assert document is not None
        self.assertEqual(document.title, "Zákoník práce")
        self.assertEqual(document.number, "262")
        self.assertEqual(document.year, 2006)

    def test_import_txt_creates_version(self) -> None:
        result = self._import_sample()

        version = legal_document_version_service.get_by_id(result.version_id)
        assert version is not None
        self.assertEqual(version.legal_document_id, result.document_id)
        self.assertEqual(version.version_name, "Aktuální znění")

    def test_import_txt_creates_sections(self) -> None:
        result = self._import_sample()

        sections = legal_section_service.list_by_version(result.version_id)
        self.assertGreater(len(sections), 0)
        paragraphs = [section for section in sections if section.paragraph == "101"]
        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(paragraphs[0].title, "Předmět úpravy")

    def test_import_txt_returns_section_count(self) -> None:
        result = self._import_sample()
        sections = legal_section_service.list_by_version(result.version_id)
        self.assertEqual(result.section_count, len(sections))
        self.assertGreater(result.section_count, 0)

    def test_import_missing_txt_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as context:
            legal_document_txt_import_service.import_from_txt(
                "/tmp/neexistuje-import.txt",
                document_type="zakon",
                title="Test",
            )
        self.assertIn("nalezen", str(context.exception).lower())

    def test_import_empty_title_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as context:
            legal_document_txt_import_service.import_from_txt(
                self.sample_path,
                document_type="zakon",
                title="   ",
            )
        self.assertIn("název", str(context.exception).lower())

    def test_import_empty_document_type_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as context:
            legal_document_txt_import_service.import_from_txt(
                self.sample_path,
                document_type="",
                title="Zákoník práce",
            )
        self.assertIn("typ", str(context.exception).lower())

    def test_import_without_sections_raises_value_error(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write("Toto je pouze volný text bez ustanovení.")
            temp_path = handle.name

        try:
            with self.assertRaises(ValueError) as context:
                legal_document_txt_import_service.import_from_txt(
                    temp_path,
                    document_type="zakon",
                    title="Prázdný předpis",
                )
            self.assertIn("ustanoven", str(context.exception).lower())
        finally:
            Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
