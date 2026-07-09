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
        SECTION_ATTACHMENT,
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.parser.legal_document_parser_models import ParsedLegalSection
    from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
        legal_section_structure_compare_service,
    )


class _SectionStub:
    def __init__(
        self,
        *,
        section_id: int,
        section_type: str,
        parent_section_id: int | None = None,
        section_number: str = "",
        paragraph: str = "",
        item_letter: str = "",
        title: str = "",
        text: str = "",
        sort_order: int = 0,
    ) -> None:
        self.id = section_id
        self.section_type = section_type
        self.parent_section_id = parent_section_id
        self.section_number = section_number
        self.paragraph = paragraph
        self.item_letter = item_letter
        self.title = title
        self.text = text
        self.sort_order = sort_order


class LegalSectionStructureCompareServiceTestCase(unittest.TestCase):
    def test_detects_new_removed_and_changed_sections(self) -> None:
        stored = [
            _SectionStub(section_id=1, section_type=SECTION_PARAGRAPH, paragraph="102", title="§ 102"),
            _SectionStub(
                section_id=2,
                section_type=SECTION_PARAGRAPH,
                paragraph="103",
                title="§ 103",
            ),
            _SectionStub(
                section_id=3,
                section_type=SECTION_SUBSECTION,
                parent_section_id=2,
                section_number="2",
            ),
            _SectionStub(
                section_id=4,
                section_type=SECTION_ATTACHMENT,
                section_number="1",
                title="Příloha č. 1",
            ),
        ]
        parsed = [
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="102",
                title="§ 102",
                sort_order=1,
            ),
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="103",
                title="§ 103 novelizovaný",
                sort_order=2,
            ),
            ParsedLegalSection(
                section_type=SECTION_SUBSECTION,
                section_number="2",
                sort_order=3,
                parent_sort_order=2,
            ),
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="104",
                title="§ 104",
                sort_order=4,
            ),
        ]

        result = legal_section_structure_compare_service.compare(
            stored_sections=stored,
            parsed_sections=parsed,
        )

        self.assertEqual([entry.log_label for entry in result.new], ["§104"])
        self.assertEqual([entry.log_label for entry in result.removed], ["Příloha č.1"])
        self.assertEqual([entry.log_label for entry in result.changed], ["§103"])
        self.assertEqual([entry.log_label for entry in result.unchanged], ["§102", "§103 odst.2"])
        self.assertTrue(result.has_structural_changes)

    def test_reports_no_structural_changes(self) -> None:
        stored = [
            _SectionStub(section_id=1, section_type=SECTION_PARAGRAPH, paragraph="102", title="§ 102"),
        ]
        parsed = [
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="102",
                title="§ 102",
                text="jiný text",
                sort_order=1,
            ),
        ]

        result = legal_section_structure_compare_service.compare(
            stored_sections=stored,
            parsed_sections=parsed,
        )

        self.assertEqual(result.new, [])
        self.assertEqual(result.removed, [])
        self.assertEqual(result.changed, [])
        self.assertEqual(len(result.unchanged), 1)
        self.assertFalse(result.has_structural_changes)

    def test_format_check_run_log_for_changed_sections(self) -> None:
        document = type(
            "DocumentStub",
            (),
            {"number": "262/2006 Sb.", "year": 2006},
        )()
        result = legal_section_structure_compare_service.compare(
            stored_sections=[
                _SectionStub(section_id=1, section_type=SECTION_PARAGRAPH, paragraph="102"),
                _SectionStub(
                    section_id=2,
                    section_type=SECTION_PARAGRAPH,
                    paragraph="103",
                ),
                _SectionStub(
                    section_id=3,
                    section_type=SECTION_SUBSECTION,
                    parent_section_id=2,
                    section_number="2",
                ),
                _SectionStub(
                    section_id=4,
                    section_type=SECTION_ATTACHMENT,
                    section_number="1",
                ),
            ],
            parsed_sections=[
                ParsedLegalSection(
                    section_type=SECTION_PARAGRAPH,
                    paragraph="102",
                    title="Nový titulek",
                    sort_order=1,
                ),
                ParsedLegalSection(
                    section_type=SECTION_PARAGRAPH,
                    paragraph="103",
                    sort_order=2,
                ),
                ParsedLegalSection(
                    section_type=SECTION_SUBSECTION,
                    section_number="2",
                    sort_order=3,
                    parent_sort_order=2,
                ),
                ParsedLegalSection(
                    section_type=SECTION_ATTACHMENT,
                    section_number="1",
                    sort_order=4,
                ),
            ],
        )

        log_text = legal_section_structure_compare_service.format_check_run_log(
            document=document,
            result=result,
        )

        self.assertIn("262/2006 Sb.", log_text)
        self.assertIn("Změněná ustanovení:", log_text)
        self.assertIn("§102", log_text)
        self.assertNotIn("Novelizace bez změny struktury ustanovení.", log_text)

    def test_format_check_run_log_without_structural_changes(self) -> None:
        document = type(
            "DocumentStub",
            (),
            {"number": "262/2006 Sb.", "year": 2006},
        )()
        result = legal_section_structure_compare_service.compare(
            stored_sections=[
                _SectionStub(section_id=1, section_type=SECTION_PARAGRAPH, paragraph="102"),
            ],
            parsed_sections=[
                ParsedLegalSection(
                    section_type=SECTION_PARAGRAPH,
                    paragraph="102",
                    sort_order=1,
                ),
            ],
        )

        log_text = legal_section_structure_compare_service.format_check_run_log(
            document=document,
            result=result,
        )

        self.assertEqual(
            log_text,
            "262/2006 Sb.\n\nNovelizace bez změny struktury ustanovení.",
        )


if __name__ == "__main__":
    unittest.main()
