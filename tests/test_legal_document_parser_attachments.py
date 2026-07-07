import unittest
from pathlib import Path

from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
    legal_document_esbirka_client,
)
from moduly.pravni_pozadavky.parser.legal_document_parser import legal_document_parser
from moduly.pravni_pozadavky.parser.legal_document_parser_diagnostics import (
    legal_document_parser_diagnostics,
)
from moduly.pravni_pozadavky.parser.legal_document_parser_models import (
    SECTION_ATTACHMENT,
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_SUBSECTION,
)


class LegalDocumentParserAttachmentsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_path = (
            Path(__file__).resolve().parent / "data" / "sample_nv_attachments.txt"
        )
        self.sample_text = self.sample_path.read_text(encoding="utf-8")
        self.fixture_390 = (
            Path(__file__).resolve().parent / "data" / "sample_esbirka_390_2021.html"
        )

    def _parse_sample(self):
        return legal_document_parser.parse_text(
            self.sample_text,
            document_type="narizeni_vlady",
            number="378",
            year=2001,
            title="Nařízení vlády č. 378/2001 Sb.",
        )

    def test_parser_recognizes_priloha_c_1(self) -> None:
        result = self._parse_sample()
        attachments = [
            section for section in result.sections if section.section_type == SECTION_ATTACHMENT
        ]

        self.assertGreaterEqual(len(attachments), 1)
        self.assertEqual(attachments[0].section_number, "1")
        self.assertEqual(
            attachments[0].title,
            "Příloha č. 1 k nařízení vlády č. 378/2001 Sb.",
        )

    def test_attachment_has_type_priloha_and_title(self) -> None:
        result = self._parse_sample()
        attachment = next(
            section for section in result.sections if section.section_type == SECTION_ATTACHMENT
        )

        self.assertEqual(attachment.section_type, SECTION_ATTACHMENT)
        self.assertTrue(attachment.title.startswith("Příloha č. 1"))

    def test_attachment_text_contains_technical_content(self) -> None:
        result = self._parse_sample()
        attachment = next(
            section for section in result.sections if section.section_type == SECTION_ATTACHMENT
        )

        self.assertIn("práce ve výškách", attachment.text)
        self.assertIn("První kategorie rizik", attachment.text)

    def test_after_attachment_start_letters_are_not_parsed_as_sections(self) -> None:
        result = self._parse_sample()
        first_attachment = next(
            section for section in result.sections if section.section_type == SECTION_ATTACHMENT
        )

        letters_after_attachment = [
            section
            for section in result.sections
            if section.section_type == SECTION_LETTER
            and section.sort_order > first_attachment.sort_order
        ]
        self.assertEqual(letters_after_attachment, [])

    def test_multiple_attachments_create_multiple_priloha_sections(self) -> None:
        result = self._parse_sample()
        attachments = [
            section for section in result.sections if section.section_type == SECTION_ATTACHMENT
        ]

        self.assertEqual(len(attachments), 2)
        self.assertEqual(attachments[0].section_number, "1")
        self.assertEqual(attachments[1].section_number, "2")
        self.assertIsNone(attachments[0].parent_sort_order)
        self.assertIsNone(attachments[1].parent_sort_order)

    def test_diagnostics_treats_attachment_as_valid_root(self) -> None:
        parse_result = legal_document_parser.parse_text(
            "Příloha č. 1 k nařízení vlády č. 378/2001 Sb.\n"
            "Technický obsah s položkami a) b) c).\n"
            "Příloha k zákonu č. 262/2006 Sb.\n"
            "Další obsah přílohy.\n",
            document_type="narizeni_vlady",
            number="378",
            year=2001,
            title="Testovací předpis",
        )
        diagnostics = legal_document_parser_diagnostics.analyze(parse_result)

        self.assertTrue(diagnostics.hierarchy_ok)
        self.assertEqual(diagnostics.counts_by_type.get(SECTION_ATTACHMENT, 0), 2)
        attachment_errors = [
            error for error in diagnostics.errors
            if error.section_type == SECTION_ATTACHMENT
        ]
        self.assertEqual(attachment_errors, [])

    def test_nv_378_style_document_has_no_hundreds_of_letters_in_tree(self) -> None:
        result = self._parse_sample()
        letters = [
            section for section in result.sections if section.section_type == SECTION_LETTER
        ]
        attachments = [
            section for section in result.sections if section.section_type == SECTION_ATTACHMENT
        ]

        self.assertEqual(len(attachments), 2)
        self.assertLess(len(letters), 10)

    def test_internet_import_390_2021_attachments_not_split_into_letters(self) -> None:
        html = self.fixture_390.read_text(encoding="utf-8")
        text = legal_document_esbirka_client.html_to_text(html)
        result = legal_document_parser.parse_text(
            text,
            document_type="narizeni_vlady",
            number="390",
            year=2021,
            title="Nařízení vlády č. 390/2021 Sb.",
        )

        attachments = [
            section for section in result.sections if section.section_type == SECTION_ATTACHMENT
        ]
        letters = [
            section for section in result.sections if section.section_type == SECTION_LETTER
        ]
        paragraphs = [
            section for section in result.sections if section.section_type == SECTION_PARAGRAPH
        ]

        self.assertGreaterEqual(len(attachments), 4)
        self.assertGreater(len(paragraphs), 0)
        self.assertLess(len(letters), 50)
        self.assertTrue(any(section.text.strip() for section in attachments))
        self.assertTrue(
            all(section.parent_sort_order is None for section in attachments),
        )

    def test_paragraphs_before_attachments_still_parse_normally(self) -> None:
        result = self._parse_sample()
        paragraphs = [
            section for section in result.sections if section.section_type == SECTION_PARAGRAPH
        ]
        subsections = [
            section for section in result.sections if section.section_type == SECTION_SUBSECTION
        ]

        self.assertEqual(len(paragraphs), 2)
        self.assertEqual(len(subsections), 2)


if __name__ == "__main__":
    unittest.main()
