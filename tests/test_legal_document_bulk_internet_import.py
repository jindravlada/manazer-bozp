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

    from moduly.pravni_pozadavky.constants import (
        DOCUMENT_TYPE_NARIZENI_VLADY,
        DOCUMENT_TYPE_ZAKON,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_bulk_internet_import_parser import (
        parse_bulk_import_line,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_bulk_internet_import_service import (
        BULK_IMPORT_STATUS_ERROR,
        BULK_IMPORT_STATUS_OK,
        BULK_IMPORT_STATUS_SKIPPED,
        DUPLICATE_SKIP_MESSAGE,
        legal_document_bulk_internet_import_service,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
        legal_document_esbirka_client,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service


class BulkInternetImportParserTestCase(unittest.TestCase):
    def test_parse_line_262_2006(self) -> None:
        parsed = parse_bulk_import_line("262/2006")

        self.assertEqual(parsed.number, "262")
        self.assertEqual(parsed.year, 2006)
        self.assertEqual(parsed.document_type, DOCUMENT_TYPE_ZAKON)

    def test_parse_line_zakon_262_2006_sb(self) -> None:
        parsed = parse_bulk_import_line("Zákon 262/2006 Sb.")

        self.assertEqual(parsed.number, "262")
        self.assertEqual(parsed.year, 2006)
        self.assertEqual(parsed.document_type, DOCUMENT_TYPE_ZAKON)

    def test_parse_line_nv_390_2021_sb(self) -> None:
        parsed = parse_bulk_import_line("NV 390/2021 Sb.")

        self.assertEqual(parsed.number, "390")
        self.assertEqual(parsed.year, 2021)
        self.assertEqual(parsed.document_type, DOCUMENT_TYPE_NARIZENI_VLADY)

    def test_parse_line_narizeni_vlady_390_2021_sb(self) -> None:
        parsed = parse_bulk_import_line("Nařízení vlády 390/2021 Sb.")

        self.assertEqual(parsed.number, "390")
        self.assertEqual(parsed.year, 2021)
        self.assertEqual(parsed.document_type, DOCUMENT_TYPE_NARIZENI_VLADY)


class BulkInternetImportServiceTestCase(unittest.TestCase):
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

        self.data_dir = Path(__file__).resolve().parent / "data"
        self.fixture_262 = self.data_dir / "sample_esbirka_262_2006.html"
        self.fixture_390 = self.data_dir / "sample_esbirka_390_2021.html"

    def _fixture_html(self, fixture_path: Path) -> str:
        return fixture_path.read_text(encoding="utf-8")

    def _fetch_side_effect(self, *, year: int, number: str) -> str:
        fixture_map = {
            (2006, "262"): self.fixture_262,
            (2021, "390"): self.fixture_390,
        }
        fixture_path = fixture_map.get((year, number))
        if fixture_path is None:
            raise ValueError("Předpis nenalezen.")
        return self._fixture_html(fixture_path)

    def test_bulk_import_continues_after_error(self) -> None:
        with patch.object(
            legal_document_esbirka_client,
            "fetch_full_text_html",
            side_effect=self._fetch_side_effect,
        ):
            summary = legal_document_bulk_internet_import_service.import_lines(
                "999/2099\n262/2006\n",
            )

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.ok_count, 1)
        self.assertEqual(summary.error_count, 1)
        self.assertEqual(summary.skipped_count, 0)
        self.assertEqual(summary.rows[0].status, BULK_IMPORT_STATUS_ERROR)
        self.assertEqual(summary.rows[1].status, BULK_IMPORT_STATUS_OK)
        self.assertEqual(summary.rows[1].regulation_label, "262/2006 Sb.")

    def test_bulk_import_skips_existing_active_document(self) -> None:
        legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262",
            year=2006,
            short_title="ZP",
        )

        with patch.object(
            legal_document_esbirka_client,
            "fetch_full_text_html",
            side_effect=self._fetch_side_effect,
        ) as fetch_mock:
            summary = legal_document_bulk_internet_import_service.import_lines("262/2006")

        fetch_mock.assert_not_called()
        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.ok_count, 0)
        self.assertEqual(summary.error_count, 0)
        self.assertEqual(summary.skipped_count, 1)
        self.assertEqual(summary.rows[0].status, BULK_IMPORT_STATUS_SKIPPED)
        self.assertEqual(summary.rows[0].error, DUPLICATE_SKIP_MESSAGE)

    def test_bulk_import_summary_counts_ok_error_skipped(self) -> None:
        legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262",
            year=2006,
            short_title="ZP",
        )

        with patch.object(
            legal_document_esbirka_client,
            "fetch_full_text_html",
            side_effect=self._fetch_side_effect,
        ):
            summary = legal_document_bulk_internet_import_service.import_lines(
                "262/2006\n999/2099\nNV 390/2021 Sb.\n",
            )

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.skipped_count, 1)
        self.assertEqual(summary.error_count, 1)
        self.assertEqual(summary.ok_count, 1)
        self.assertEqual(summary.rows[0].status, BULK_IMPORT_STATUS_SKIPPED)
        self.assertEqual(summary.rows[1].status, BULK_IMPORT_STATUS_ERROR)
        self.assertEqual(summary.rows[2].status, BULK_IMPORT_STATUS_OK)
        self.assertEqual(summary.rows[2].regulation_label, "390/2021 Sb.")
        self.assertGreater(summary.rows[2].section_count or 0, 0)
        self.assertTrue(summary.rows[2].title)


if __name__ == "__main__":
    unittest.main()
