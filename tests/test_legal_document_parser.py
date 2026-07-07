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
    from moduly.pravni_pozadavky.parser.legal_document_parser_diagnostics import (
        legal_document_parser_diagnostics,
    )
    from moduly.pravni_pozadavky.parser.legal_document_parser_models import (
        SECTION_DIVISION,
        SECTION_HEAD,
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_PART,
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

    def _section_has_import_content(self, section) -> bool:
        section_number = (section.section_number or "").strip()
        paragraph = (section.paragraph or "").strip()
        item_letter = (section.item_letter or "").strip()
        title = (section.title or "").strip()
        text = (section.text or "").strip()

        if section.section_type == SECTION_PARAGRAPH:
            return bool(title or text or paragraph)
        if section.section_type == SECTION_SUBSECTION:
            return bool(section_number or text)
        if section.section_type == SECTION_LETTER:
            return bool(item_letter or text)
        return bool(section_number or title or text)

    def test_realistic_sample_has_no_empty_sections(self) -> None:
        result = self._parse_sample()

        self.assertGreater(len(result.sections), 0)
        for section in result.sections:
            self.assertTrue(
                self._section_has_import_content(section),
                f"Prázdná sekce: {section.section_type} "
                f"number={section.section_number!r} "
                f"title={section.title!r} "
                f"text={section.text!r}",
            )

        section_types = {section.section_type for section in result.sections}
        self.assertIn(SECTION_PART, section_types)
        self.assertIn(SECTION_HEAD, section_types)
        self.assertIn(SECTION_DIVISION, section_types)
        self.assertIn(SECTION_PARAGRAPH, section_types)

        paragraphs = {section.paragraph for section in result.sections if section.section_type == SECTION_PARAGRAPH}
        self.assertIn("101", paragraphs)
        self.assertIn("102", paragraphs)
        self.assertNotIn("999", paragraphs)

    def test_realistic_sample_imports_without_validation_error(self) -> None:
        result = self._parse_sample()
        import_result = legal_document_json_import_service.import_data(result.to_dict())
        self.assertGreater(import_result.section_count, 0)

    def test_sample_zakonik_prace_parser_import_to_database(self) -> None:
        result = self._parse_sample()
        import_result = legal_document_json_import_service.import_data(result.to_dict())
        db_sections = legal_section_service.list_by_version(import_result.version_id)

        self.assertEqual(import_result.section_count, len(result.sections))
        self.assertEqual(len(db_sections), len(result.sections))
        self.assertGreater(len(db_sections), 0)

        paragraph = next(item for item in db_sections if item.paragraph == "101")
        self.assertEqual(paragraph.title, "Předmět úpravy")

    def test_bare_paragraph_from_parser_imports_without_validation_error(self) -> None:
        result = self._parse_fragment(
            "ČÁST I\n"
            "§ 1\n"
            "a) první písmeno,\n"
            "b) druhé písmeno.\n",
        )
        import_result = legal_document_json_import_service.import_data(result.to_dict())
        db_sections = legal_section_service.list_by_version(import_result.version_id)

        self.assertEqual(import_result.section_count, len(result.sections))
        bare_paragraph = next(section for section in db_sections if section.paragraph == "1")
        self.assertEqual(bare_paragraph.title, "")
        self.assertEqual(bare_paragraph.text, "")

    def _section_by_sort(self, sections, sort_order: int):
        return next(section for section in sections if section.sort_order == sort_order)

    def test_head_parent_is_part(self) -> None:
        result = self._parse_sample()
        part = self._section_by_sort(result.sections, 1)
        head = self._section_by_sort(result.sections, 2)

        self.assertEqual(part.section_type, SECTION_PART)
        self.assertEqual(head.section_type, SECTION_HEAD)
        self.assertIsNone(part.parent_sort_order)
        self.assertEqual(head.parent_sort_order, part.sort_order)

    def test_paragraph_parent_is_division(self) -> None:
        result = self._parse_sample()
        division = self._section_by_sort(result.sections, 3)
        paragraph = self._section_by_sort(result.sections, 4)

        self.assertEqual(division.section_type, SECTION_DIVISION)
        self.assertEqual(paragraph.section_type, SECTION_PARAGRAPH)
        self.assertEqual(paragraph.parent_sort_order, division.sort_order)

    def test_subsection_parent_is_paragraph(self) -> None:
        result = self._parse_sample()
        paragraph = self._section_by_sort(result.sections, 4)
        subsection = self._section_by_sort(result.sections, 5)

        self.assertEqual(subsection.section_type, SECTION_SUBSECTION)
        self.assertEqual(subsection.parent_sort_order, paragraph.sort_order)

    def test_letter_parent_is_subsection(self) -> None:
        result = self._parse_sample()
        subsection = self._section_by_sort(result.sections, 6)
        letter = self._section_by_sort(result.sections, 7)

        self.assertEqual(letter.section_type, SECTION_LETTER)
        self.assertEqual(letter.parent_sort_order, subsection.sort_order)

    def test_import_sets_parent_section_id(self) -> None:
        result = self._parse_sample()
        import_result = legal_document_json_import_service.import_data(result.to_dict())
        db_sections = legal_section_service.list_by_version(import_result.version_id)

        sort_order_to_id = {section.sort_order: section.id for section in db_sections}
        parsed_by_sort = {section.sort_order: section for section in result.sections}

        for db_section in db_sections:
            parsed_section = parsed_by_sort.get(db_section.sort_order)
            assert parsed_section is not None
            if parsed_section.parent_sort_order is None:
                self.assertIsNone(db_section.parent_section_id)
            else:
                expected_parent_id = sort_order_to_id.get(parsed_section.parent_sort_order)
                self.assertEqual(db_section.parent_section_id, expected_parent_id)

    def _parse_fragment(self, text: str):
        return legal_document_parser.parse_text(
            text,
            document_type="zakon",
            number="262",
            year=2006,
            title="Zákoník práce",
        )

    def test_subsection_after_paragraph_has_paragraph_parent(self) -> None:
        result = self._parse_fragment(
            "ČÁST I\n"
            "§ 101\n"
            "(1) Text prvního odstavce.\n",
        )
        paragraph = next(section for section in result.sections if section.section_type == SECTION_PARAGRAPH)
        subsection = next(section for section in result.sections if section.section_type == SECTION_SUBSECTION)

        self.assertEqual(subsection.parent_sort_order, paragraph.sort_order)

    def test_letter_after_subsection_has_subsection_parent(self) -> None:
        result = self._parse_fragment(
            "ČÁST I\n"
            "§ 101\n"
            "(1) Text odstavce.\n"
            "a) Text písmene.\n",
        )
        subsection = next(section for section in result.sections if section.section_type == SECTION_SUBSECTION)
        letter = next(section for section in result.sections if section.section_type == SECTION_LETTER)

        self.assertEqual(letter.parent_sort_order, subsection.sort_order)

    def test_text_between_paragraph_and_subsection_keeps_paragraph_parent(self) -> None:
        result = self._parse_fragment(
            "ČÁST I\n"
            "§ 101\n"
            "Předmět úpravy\n"
            "doplňující text paragrafu\n"
            "(1) Text odstavce.\n",
        )
        paragraph = next(section for section in result.sections if section.section_type == SECTION_PARAGRAPH)
        subsection = next(section for section in result.sections if section.section_type == SECTION_SUBSECTION)

        self.assertEqual(paragraph.title, "Předmět úpravy")
        self.assertIn("doplňující text paragrafu", paragraph.text)
        self.assertEqual(subsection.parent_sort_order, paragraph.sort_order)

    def test_text_between_subsection_and_letter_keeps_subsection_parent(self) -> None:
        result = self._parse_fragment(
            "ČÁST I\n"
            "§ 101\n"
            "(1) Text odstavce.\n"
            "pokračování odstavce\n"
            "a) Text písmene.\n",
        )
        subsection = next(section for section in result.sections if section.section_type == SECTION_SUBSECTION)
        letter = next(section for section in result.sections if section.section_type == SECTION_LETTER)

        self.assertIn("pokračování odstavce", subsection.text)
        self.assertEqual(letter.parent_sort_order, subsection.sort_order)

    def test_realistic_sample_has_no_subsection_without_parent(self) -> None:
        result = self._parse_sample()
        diagnostics = legal_document_parser_diagnostics.analyze(result)

        self.assertTrue(diagnostics.hierarchy_ok)
        subsection_errors = [
            error
            for error in diagnostics.errors
            if error.section_type == SECTION_SUBSECTION
        ]
        self.assertEqual(subsection_errors, [])
        for section in result.sections:
            if section.section_type == SECTION_SUBSECTION:
                self.assertIsNotNone(section.parent_sort_order)


if __name__ == "__main__":
    unittest.main()
