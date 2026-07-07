import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
        legal_document_esbirka_client,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_internet_import_service import (
        legal_document_internet_import_service,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_txt_import_service import (
        legal_document_txt_import_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalDocumentInternetImportTestCase(unittest.TestCase):
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

    def _import_via_txt_from_html(
        self,
        fixture_path: Path,
        *,
        document_type: str,
        number: str,
        year: int,
    ):
        html = self._fixture_html(fixture_path)
        text = legal_document_esbirka_client.html_to_text(html)
        title = legal_document_esbirka_client.extract_title(html)

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write(text)
            temp_path = handle.name

        try:
            return legal_document_txt_import_service.import_from_txt(
                temp_path,
                document_type=document_type,
                number=number,
                year=year,
                title=title,
                short_title="",
            )
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _import_via_internet_mock(
        self,
        fixture_path: Path,
        *,
        document_type: str,
        number: str,
        year: int,
    ):
        html = self._fixture_html(fixture_path)
        with patch.object(
            legal_document_esbirka_client,
            "fetch_full_text_html",
            return_value=html,
        ):
            return legal_document_internet_import_service.import_from_internet(
                document_type=document_type,
                number=number,
                year=year,
            )

    def _section_snapshot(self, version_id: int) -> list[tuple]:
        sections = legal_section_service.list_by_version(version_id)
        return [
            (
                section.section_type,
                section.section_number,
                section.paragraph,
                section.item_letter,
                section.title,
                section.text,
                section.parent_section_id,
                section.sort_order,
            )
            for section in sections
        ]

    def test_html_to_text_extracts_title_for_262_2006(self) -> None:
        html = self._fixture_html(self.fixture_262)
        title = legal_document_esbirka_client.extract_title(html)
        self.assertEqual(title, "Zákon zákoník práce")

    def test_html_to_text_extracts_title_for_390_2021(self) -> None:
        html = self._fixture_html(self.fixture_390)
        title = legal_document_esbirka_client.extract_title(html)
        self.assertIn("osobních ochranných pracovních prostředků", title)

    def test_internet_import_262_2006_matches_txt_import(self) -> None:
        txt_result = self._import_via_txt_from_html(
            self.fixture_262,
            document_type="zakon",
            number="262",
            year=2006,
        )
        txt_sections = self._section_snapshot(txt_result.version_id)

        self._clear_database()
        internet_result = self._import_via_internet_mock(
            self.fixture_262,
            document_type="zakon",
            number="262",
            year=2006,
        )
        internet_sections = self._section_snapshot(internet_result.version_id)

        self.assertEqual(internet_result.section_count, txt_result.section_count)
        self.assertEqual(internet_sections, txt_sections)

        document = legal_document_service.get_by_id(internet_result.document_id)
        assert document is not None
        self.assertEqual(document.number, "262")
        self.assertEqual(document.year, 2006)

        paragraphs = [section for section in internet_sections if section[2] == "101"]
        self.assertEqual(len(paragraphs), 1)

    def test_internet_import_390_2021_matches_txt_import(self) -> None:
        txt_result = self._import_via_txt_from_html(
            self.fixture_390,
            document_type="narizeni_vlady",
            number="390",
            year=2021,
        )
        txt_sections = self._section_snapshot(txt_result.version_id)

        self._clear_database()
        internet_result = self._import_via_internet_mock(
            self.fixture_390,
            document_type="narizeni_vlady",
            number="390",
            year=2021,
        )
        internet_sections = self._section_snapshot(internet_result.version_id)

        self.assertEqual(internet_result.section_count, txt_result.section_count)
        self.assertEqual(internet_sections, txt_sections)

        document = legal_document_service.get_by_id(internet_result.document_id)
        assert document is not None
        self.assertEqual(document.number, "390")
        self.assertEqual(document.year, 2021)

    def test_fetch_not_found_raises_value_error(self) -> None:
        with patch("requests.get") as get_mock:
            response = get_mock.return_value
            response.raise_for_status.return_value = None
            response.text = "<html><body><h1>Stránka nenalezena</h1></body></html>"
            with self.assertRaises(ValueError) as context:
                legal_document_esbirka_client.fetch_full_text_html(year=1999, number="99999")
        self.assertEqual(str(context.exception), "Předpis nenalezen.")

    def test_fetch_network_error_raises_value_error(self) -> None:
        with patch(
            "requests.get",
            side_effect=requests.ConnectionError("offline"),
        ):
            with self.assertRaises(ValueError) as context:
                legal_document_esbirka_client.fetch_full_text_html(year=2006, number="262")
        self.assertEqual(str(context.exception), "Internet není dostupný.")

    def test_html_without_frags_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as context:
            legal_document_esbirka_client.html_to_text("<html><body>bez obsahu</body></html>")
        self.assertEqual(str(context.exception), "Neočekávaný formát stránky.")

    def test_import_reports_progress_statuses(self) -> None:
        html = self._fixture_html(self.fixture_390)
        statuses: list[str] = []
        with patch.object(
            legal_document_esbirka_client,
            "fetch_full_text_html",
            return_value=html,
        ):
            legal_document_internet_import_service.import_from_internet(
                document_type="narizeni_vlady",
                number="390",
                year=2021,
                on_status=statuses.append,
            )

        self.assertEqual(
            statuses,
            [
                "Vyhledávám předpis...",
                "Stahuji...",
                "Převádím...",
                "Importuji...",
                "Hotovo.",
            ],
        )

    def test_import_without_document_type_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as context:
            legal_document_internet_import_service.import_from_internet(
                document_type="",
                number="262",
                year=2006,
            )
        self.assertIn("typ", str(context.exception).lower())

    def _clear_database(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
