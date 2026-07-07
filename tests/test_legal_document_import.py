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

    from moduly.pravni_pozadavky.import_export.legal_document_json_export_service import (
        legal_document_json_export_service,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
        legal_document_json_import_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalDocumentJsonImportTestCase(unittest.TestCase):
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

        self.sample_path = (
            Path(__file__).resolve().parents[1]
            / "moduly"
            / "pravni_pozadavky"
            / "import_export"
            / "sample_legal_document_import.json"
        )

    def test_import_creates_document(self) -> None:
        result = legal_document_json_import_service.import_from_file(self.sample_path)

        document = legal_document_service.get_by_id(result.document_id)
        assert document is not None
        self.assertEqual(document.title, "Nařízení vlády č. 390/2021 Sb.")
        self.assertEqual(document.number, "390")
        self.assertEqual(document.year, 2021)

    def test_import_creates_version(self) -> None:
        result = legal_document_json_import_service.import_from_file(self.sample_path)

        version = legal_document_version_service.get_by_id(result.version_id)
        assert version is not None
        self.assertEqual(version.legal_document_id, result.document_id)
        self.assertEqual(version.version_name, "Aktuální znění")

    def test_import_creates_sections(self) -> None:
        result = legal_document_json_import_service.import_from_file(self.sample_path)

        sections = legal_section_service.list_by_version(result.version_id)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].title, "Předmět úpravy")
        self.assertEqual(sections[0].paragraph, "1")

    def test_import_returns_section_count(self) -> None:
        result = legal_document_json_import_service.import_from_file(self.sample_path)
        self.assertEqual(result.section_count, 1)

    def test_import_missing_file_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as context:
            legal_document_json_import_service.import_from_file("/tmp/neexistuje-import.json")
        self.assertIn("nalezen", str(context.exception).lower())

    def test_import_invalid_json_raises_value_error(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            handle.write("{ neplatny json")
            temp_path = handle.name

        try:
            with self.assertRaises(ValueError) as context:
                legal_document_json_import_service.import_from_file(temp_path)
            self.assertIn("json", str(context.exception).lower())
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_import_without_document_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as context:
            legal_document_json_import_service.import_data({"version": {}, "sections": []})
        self.assertIn("document", str(context.exception).lower())

    def test_import_without_version_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as context:
            legal_document_json_import_service.import_data(
                {"document": {"document_type": "zakon", "title": "Test"}, "sections": []},
            )
        self.assertIn("version", str(context.exception).lower())

    def test_import_with_sections_not_list_raises_value_error(self) -> None:
        payload = {
            "document": {"document_type": "zakon", "title": "Test"},
            "version": {"version_name": "Verze"},
            "sections": "ne-seznam",
        }
        with self.assertRaises(ValueError) as context:
            legal_document_json_import_service.import_data(payload)
        self.assertIn("seznam", str(context.exception).lower())

    def test_import_from_dict_with_multiple_sections(self) -> None:
        payload = {
            "document": {
                "document_type": "zakon",
                "title": "Testovací zákon",
                "number": "1",
                "year": 2024,
            },
            "version": {
                "version_name": "Verze 1",
            },
            "sections": [
                {
                    "section_type": "paragraf",
                    "paragraph": "1",
                    "title": "První",
                    "sort_order": 1,
                },
                {
                    "section_type": "paragraf",
                    "paragraph": "2",
                    "title": "Druhý",
                    "sort_order": 2,
                },
            ],
        }
        result = legal_document_json_import_service.import_data(payload)
        self.assertEqual(result.section_count, 2)
        sections = legal_section_service.list_by_version(result.version_id)
        self.assertEqual(len(sections), 2)


class LegalDocumentJsonExportTestCase(unittest.TestCase):
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

        self.sample_path = (
            Path(__file__).resolve().parents[1]
            / "moduly"
            / "pravni_pozadavky"
            / "import_export"
            / "sample_legal_document_import.json"
        )

    def _import_sample(self):
        return legal_document_json_import_service.import_from_file(self.sample_path)

    def test_export_creates_json_file(self) -> None:
        import_result = self._import_sample()

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            temp_path = handle.name

        try:
            legal_document_json_export_service.export_to_file(import_result.document_id, temp_path)
            exported_text = Path(temp_path).read_text(encoding="utf-8")
            exported_data = json.loads(exported_text)
            self.assertIsInstance(exported_data, dict)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_export_contains_document(self) -> None:
        import_result = self._import_sample()
        data = legal_document_json_export_service.build_data(import_result.document_id)

        self.assertIn("document", data)
        self.assertEqual(data["document"]["title"], "Nařízení vlády č. 390/2021 Sb.")
        self.assertEqual(data["document"]["number"], "390")
        self.assertEqual(data["document"]["year"], 2021)

    def test_export_contains_version(self) -> None:
        import_result = self._import_sample()
        data = legal_document_json_export_service.build_data(import_result.document_id)

        self.assertIn("version", data)
        self.assertEqual(data["version"]["version_name"], "Aktuální znění")

    def test_export_contains_sections(self) -> None:
        import_result = self._import_sample()
        data = legal_document_json_export_service.build_data(import_result.document_id)

        self.assertIn("sections", data)
        self.assertEqual(len(data["sections"]), 1)
        self.assertEqual(data["sections"][0]["title"], "Předmět úpravy")
        self.assertEqual(data["sections"][0]["paragraph"], "1")

    def test_export_empty_sections(self) -> None:
        document = legal_document_service.create(
            document_type="zakon",
            title="Zákon bez částí",
        )
        legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 1",
        )

        data = legal_document_json_export_service.build_data(document.id)
        self.assertEqual(data["sections"], [])

    def test_export_without_active_version_raises_value_error(self) -> None:
        document = legal_document_service.create(
            document_type="zakon",
            title="Zákon bez verze",
        )

        with self.assertRaises(ValueError) as context:
            legal_document_json_export_service.build_data(document.id)
        self.assertIn("verzi", str(context.exception).lower())

    def test_export_import_round_trip_creates_matching_document(self) -> None:
        import_result = self._import_sample()
        original_document = legal_document_service.get_by_id(import_result.document_id)
        original_version = legal_document_version_service.get_by_id(import_result.version_id)
        original_sections = legal_section_service.list_by_version(import_result.version_id)
        assert original_document is not None
        assert original_version is not None

        exported_data = legal_document_json_export_service.build_data(import_result.document_id)

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

        round_trip_result = legal_document_json_import_service.import_data(exported_data)
        imported_document = legal_document_service.get_by_id(round_trip_result.document_id)
        imported_version = legal_document_version_service.get_by_id(round_trip_result.version_id)
        imported_sections = legal_section_service.list_by_version(round_trip_result.version_id)
        assert imported_document is not None
        assert imported_version is not None

        self.assertEqual(imported_document.document_type, original_document.document_type)
        self.assertEqual(imported_document.title, original_document.title)
        self.assertEqual(imported_document.number, original_document.number)
        self.assertEqual(imported_document.year, original_document.year)
        self.assertEqual(imported_document.short_title, original_document.short_title)
        self.assertEqual(imported_version.version_name, original_version.version_name)
        self.assertEqual(len(imported_sections), len(original_sections))
        self.assertEqual(imported_sections[0].title, original_sections[0].title)
        self.assertEqual(imported_sections[0].paragraph, original_sections[0].paragraph)
        self.assertEqual(imported_sections[0].text, original_sections[0].text)


if __name__ == "__main__":
    unittest.main()
