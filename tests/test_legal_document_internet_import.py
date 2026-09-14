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
    from moduly.pravni_pozadavky.constants import SECTION_LETTER, SECTION_PARAGRAPH, SECTION_SUBSECTION


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
        self.assertEqual(document.document_type, "narizeni_vlady")

    def test_fetch_not_found_raises_value_error(self) -> None:
        from core.http_safe import SafeHttpsResponse

        html = "<html><body><h1>Stránka nenalezena</h1></body></html>"
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_client.safe_https_get",
            return_value=SafeHttpsResponse(
                status_code=200,
                body=html.encode("utf-8"),
                final_url="https://www.esbirka.cz/cs/1999-99999",
            ),
        ):
            with self.assertRaises(ValueError) as context:
                legal_document_esbirka_client.fetch_full_text_html(year=1999, number="99999")
        self.assertEqual(str(context.exception), "Předpis nenalezen.")

    def test_fetch_network_error_raises_value_error(self) -> None:
        from core.http_safe import SafeHttpsError

        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_client.safe_https_get",
            side_effect=SafeHttpsError("Služba není dostupná.", kind="network"),
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
                "Parsuji...",
                "Ukládám...",
                "Hotovo.",
            ],
        )

    def _paragraph_sections(self, version_id: int, *, paragraph_numbers: set[str] | None = None):
        sections = legal_section_service.list_by_version(version_id)
        paragraphs = [
            section
            for section in sections
            if section.section_type == SECTION_PARAGRAPH
        ]
        if paragraph_numbers is None:
            return paragraphs
        return [section for section in paragraphs if section.paragraph in paragraph_numbers]

    def test_html_to_text_390_2021_contains_paragraph_bodies(self) -> None:
        html = self._fixture_html(self.fixture_390)
        text = legal_document_esbirka_client.html_to_text(html)

        self.assertIn("§ 1", text)
        self.assertIn("Toto nařízení zapracovává příslušné předpisy Evropské unie", text)
        self.assertIn("§ 2", text)
        self.assertIn("Osobním ochranným pracovním prostředkem pro účely tohoto nařízení není", text)
        self.assertIn("§ 7", text)
        self.assertIn("Toto nařízení nabývá účinnosti dnem 1. listopadu 2021.", text)

    def test_html_to_text_can_save_debug_txt(self) -> None:
        html = self._fixture_html(self.fixture_390)
        with tempfile.TemporaryDirectory() as temp_dir:
            debug_path = Path(temp_dir) / "predpis.txt"
            legal_document_esbirka_client.html_to_text(html, debug_txt_path=debug_path)
            saved_text = debug_path.read_text(encoding="utf-8")
        self.assertIn("§ 1", saved_text)
        self.assertIn("Toto nařízení zapracovává", saved_text)

    def _paragraph_has_content(self, section, sections) -> bool:
        if section.text.strip() or section.title.strip():
            return True
        return any(child.parent_section_id == section.id for child in sections)

    def test_internet_import_390_2021_paragraphs_have_text(self) -> None:
        result = self._import_via_internet_mock(
            self.fixture_390,
            document_type="narizeni_vlady",
            number="390",
            year=2021,
        )

        sections = legal_section_service.list_by_version(result.version_id)
        main_paragraphs = self._paragraph_sections(
            result.version_id,
            paragraph_numbers={"1", "2", "3", "4", "5", "6", "7"},
        )
        self.assertEqual(len(main_paragraphs), 7)

        paragraph_one = next(section for section in main_paragraphs if section.paragraph == "1")
        paragraph_two = next(section for section in main_paragraphs if section.paragraph == "2")
        self.assertTrue(paragraph_one.title.strip() or paragraph_one.text.strip())
        self.assertTrue(paragraph_two.title.strip() or paragraph_two.text.strip())

        empty_main_paragraphs = [
            section
            for section in main_paragraphs
            if not self._paragraph_has_content(section, sections)
        ]
        self.assertEqual(empty_main_paragraphs, [])

    def test_html_to_text_390_2021_section_3_has_letter_lines(self) -> None:
        html = self._fixture_html(self.fixture_390)
        text = legal_document_esbirka_client.html_to_text(html)

        section_three_start = text.find("§ 3\n")
        section_four_start = text.find("§ 4\n")
        self.assertGreaterEqual(section_three_start, 0)
        self.assertGreater(section_four_start, section_three_start)
        section_three_text = text[section_three_start:section_four_start]

        self.assertIn("(1) Osobní ochranný pracovní prostředek musí", section_three_text)
        self.assertIn("a) být po dobu používání účinný", section_three_text)
        self.assertIn("b) odpovídat podmínkám na pracovišti,", section_three_text)
        self.assertIn("c) být přizpůsoben fyzickým předpokladům zaměstnance a", section_three_text)

    def test_internet_import_390_2021_section_3_subsection_has_letters(self) -> None:
        result = self._import_via_internet_mock(
            self.fixture_390,
            document_type="narizeni_vlady",
            number="390",
            year=2021,
        )

        sections = legal_section_service.list_by_version(result.version_id)
        paragraph_three = next(
            section
            for section in sections
            if section.section_type == SECTION_PARAGRAPH and section.paragraph == "3"
        )
        subsection_one = next(
            section
            for section in sections
            if (
                section.section_type == SECTION_SUBSECTION
                and section.section_number == "1"
                and section.parent_section_id == paragraph_three.id
            )
        )
        letters = [
            section
            for section in sections
            if section.section_type == SECTION_LETTER and section.parent_section_id == subsection_one.id
        ]

        self.assertEqual(len(letters), 4)
        letter_a = next(section for section in letters if section.item_letter == "a")
        self.assertTrue(letter_a.text.strip())
        self.assertIn("účinný", letter_a.text)

    def test_internet_import_390_2021_has_letters_under_paragraphs(self) -> None:
        result = self._import_via_internet_mock(
            self.fixture_390,
            document_type="narizeni_vlady",
            number="390",
            year=2021,
        )

        sections = legal_section_service.list_by_version(result.version_id)
        letters = [section for section in sections if section.section_type == SECTION_LETTER]
        self.assertGreater(len(letters), 0)
        self.assertTrue(any(section.text.strip() for section in letters))

        paragraph_two = next(
            section
            for section in sections
            if section.section_type == SECTION_PARAGRAPH and section.paragraph == "2"
        )
        paragraph_two_letters = [
            section
            for section in letters
            if section.parent_section_id == paragraph_two.id
        ]
        self.assertGreaterEqual(len(paragraph_two_letters), 7)

    def test_internet_import_detects_document_type_from_title_even_if_explicit_is_wrong(self) -> None:
        result = self._import_via_internet_mock(
            self.fixture_390,
            document_type="zakon",
            number="390",
            year=2021,
        )
        document = legal_document_service.get_by_id(result.document_id)
        assert document is not None
        self.assertEqual(document.document_type, "narizeni_vlady")

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
