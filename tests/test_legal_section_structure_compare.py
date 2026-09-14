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
        SECTION_PART,
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
        self.assertNotIn("Novelizace bez změny ustanovení.", log_text)

    def test_format_check_run_summary(self) -> None:
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

        summary = legal_section_structure_compare_service.format_check_run_summary(
            document=document,
            result=result,
        )

        self.assertEqual(
            summary,
            "262/2006 Sb. – novelizace bez změny ustanovení.",
        )

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
            "262/2006 Sb.\n\nNovelizace bez změny ustanovení.",
        )

    def test_version_compare_detects_text_only_change(self) -> None:
        old_sections = [
            _SectionStub(
                section_id=1,
                section_type=SECTION_PARAGRAPH,
                paragraph="5",
                title="§ 5",
                text="Původní text ustanovení",
            ),
        ]
        new_sections = [
            _SectionStub(
                section_id=11,
                section_type=SECTION_PARAGRAPH,
                paragraph="5",
                title="§ 5",
                text="Nový text téhož ustanovení",
            ),
        ]

        result = legal_section_structure_compare_service.compare_version_sections(
            old_sections=old_sections,
            new_sections=new_sections,
        )

        self.assertEqual(result.new, [])
        self.assertEqual(result.removed, [])
        self.assertEqual(len(result.changed), 1)
        changed = result.changed[0]
        self.assertEqual(changed.identity_key, "§:5")
        self.assertEqual(changed.old_text, "Původní text ustanovení")
        self.assertEqual(changed.new_text, "Nový text téhož ustanovení")

    def test_version_compare_ignores_whitespace_only_difference(self) -> None:
        old_sections = [
            _SectionStub(
                section_id=1,
                section_type=SECTION_PARAGRAPH,
                paragraph="5",
                text="Stejný  obsah\nustanovení",
            ),
        ]
        new_sections = [
            _SectionStub(
                section_id=11,
                section_type=SECTION_PARAGRAPH,
                paragraph="5",
                text="Stejný obsah ustanovení",
            ),
        ]

        result = legal_section_structure_compare_service.compare_version_sections(
            old_sections=old_sections,
            new_sections=new_sections,
        )

        self.assertEqual(result.changed, [])
        self.assertEqual(result.new, [])
        self.assertEqual(result.removed, [])
        self.assertEqual(len(result.unchanged), 1)

    def test_version_compare_added_and_removed_keep_own_text(self) -> None:
        old_sections = [
            _SectionStub(
                section_id=1,
                section_type=SECTION_PARAGRAPH,
                paragraph="12a",
                title="Mladiství žáci smějí pouze v rámci přípravy",
                text="",
            ),
            _SectionStub(
                section_id=2,
                section_type=SECTION_LETTER,
                parent_section_id=1,
                item_letter="a",
                text="původní písmeno a",
            ),
        ]
        new_sections = [
            _SectionStub(
                section_id=11,
                section_type=SECTION_PARAGRAPH,
                paragraph="7a",
                title="§ 7a",
                text="nově přidané ustanovení",
            ),
        ]

        result = legal_section_structure_compare_service.compare_version_sections(
            old_sections=old_sections,
            new_sections=new_sections,
        )

        self.assertEqual([entry.log_label for entry in result.new], ["§7a"])
        self.assertEqual(result.new[0].old_text, None)
        self.assertEqual(result.new[0].new_text, "nově přidané ustanovení")
        removed_by_key = {entry.identity_key: entry for entry in result.removed}
        self.assertEqual(removed_by_key["§:12a"].old_text, "Mladiství žáci smějí pouze v rámci přípravy")
        self.assertIsNone(removed_by_key["§:12a"].new_text)
        self.assertEqual(removed_by_key["§:12a/pism:a"].old_text, "původní písmeno a")
        self.assertIsNone(removed_by_key["§:12a/pism:a"].new_text)

    def test_version_compare_does_not_mark_parent_when_only_letter_text_changes(self) -> None:
        old_sections = [
            _SectionStub(
                section_id=1,
                section_type=SECTION_PARAGRAPH,
                paragraph="5",
                title="Nadpis paragrafu",
                text="",
            ),
            _SectionStub(
                section_id=2,
                section_type=SECTION_SUBSECTION,
                parent_section_id=1,
                section_number="2",
                text="odstavec beze změny",
            ),
            _SectionStub(
                section_id=3,
                section_type=SECTION_LETTER,
                parent_section_id=2,
                item_letter="a",
                text="původní písmeno",
            ),
        ]
        new_sections = [
            _SectionStub(
                section_id=11,
                section_type=SECTION_PARAGRAPH,
                paragraph="5",
                title="Nadpis paragrafu",
                text="",
            ),
            _SectionStub(
                section_id=12,
                section_type=SECTION_SUBSECTION,
                parent_section_id=11,
                section_number="2",
                text="odstavec beze změny",
            ),
            _SectionStub(
                section_id=13,
                section_type=SECTION_LETTER,
                parent_section_id=12,
                item_letter="a",
                text="nové písmeno",
            ),
        ]

        result = legal_section_structure_compare_service.compare_version_sections(
            old_sections=old_sections,
            new_sections=new_sections,
        )

        self.assertEqual([entry.identity_key for entry in result.changed], ["§:5/odst:2/pism:a"])
        self.assertEqual(result.new, [])
        self.assertEqual(result.removed, [])
        self.assertEqual(len(result.unchanged), 2)

    def test_canonical_equal_ignores_hierarchy_split_and_part_labels(self) -> None:
        stored = [
            _SectionStub(
                section_id=1,
                section_type=SECTION_PART,
                section_number="I",
                text="ÚVODNÍ USTANOVENÍ",
            ),
            _SectionStub(
                section_id=2,
                section_type=SECTION_PARAGRAPH,
                parent_section_id=1,
                paragraph="1",
                title="Předmět úpravy",
                text="Tento zákon upravuje silniční dopravu.",
            ),
        ]
        parsed = [
            ParsedLegalSection(
                section_type=SECTION_PART,
                section_number="PRVNÍ",
                text="ÚVODNÍ USTANOVENÍ",
                sort_order=1,
            ),
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="1",
                title="Předmět úpravy",
                sort_order=2,
                parent_sort_order=1,
            ),
            ParsedLegalSection(
                section_type=SECTION_SUBSECTION,
                section_number="1",
                text="Tento zákon upravuje silniční dopravu.",
                sort_order=3,
                parent_sort_order=2,
            ),
        ]
        self.assertTrue(
            legal_section_structure_compare_service.trees_content_equal(
                stored_sections=stored,
                parsed_sections=parsed,
            ),
        )

    def test_canonical_equal_ignores_whitespace_and_formatting(self) -> None:
        stored = [
            _SectionStub(
                section_id=1,
                section_type=SECTION_PARAGRAPH,
                paragraph="1",
                text="Pokuta 10 000 Kč. 1. stavební úřad 2. žádost.",
            ),
        ]
        parsed = [
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="1",
                text="Pokuta 10000 Kč. 2. žádost. 1. stavební úřad",
                sort_order=1,
            ),
        ]
        self.assertTrue(
            legal_section_structure_compare_service.trees_content_equal(
                stored_sections=stored,
                parsed_sections=parsed,
            ),
        )

    def test_canonical_detects_real_wording_change(self) -> None:
        stored = [
            _SectionStub(
                section_id=1,
                section_type=SECTION_PARAGRAPH,
                paragraph="1",
                text="Zaměstnanec musí používat ochranné pomůcky.",
            ),
        ]
        parsed = [
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="1",
                text="Zaměstnanec může používat ochranné pomůcky.",
                sort_order=1,
            ),
        ]
        self.assertFalse(
            legal_section_structure_compare_service.trees_content_equal(
                stored_sections=stored,
                parsed_sections=parsed,
            ),
        )

    def test_canonical_equal_ignores_leaked_oddil_heading(self) -> None:
        stored = [
            _SectionStub(
                section_id=1,
                section_type=SECTION_PARAGRAPH,
                paragraph="96",
                text="Práce na zařízení vysokého napětí. Oddíl čtvrtý Zvláštní ustanovení",
            ),
        ]
        parsed = [
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="96",
                text="Práce na zařízení vysokého napětí.",
                sort_order=1,
            ),
        ]
        self.assertTrue(
            legal_section_structure_compare_service.trees_content_equal(
                stored_sections=stored,
                parsed_sections=parsed,
            ),
        )

    def test_canonical_detects_removed_361_style_paragraph(self) -> None:
        stored = [
            _SectionStub(
                section_id=1,
                section_type=SECTION_PART,
                section_number="DRUHÁ",
                text="RIZIKOVÉ FAKTORY",
            ),
            _SectionStub(
                section_id=2,
                section_type=SECTION_PARAGRAPH,
                parent_section_id=1,
                paragraph="12",
                text="Hodnocení rizik se provádí podle přílohy.",
            ),
            _SectionStub(
                section_id=3,
                section_type=SECTION_PARAGRAPH,
                parent_section_id=1,
                paragraph="12a",
                title="Mladiství žáci smějí pouze v rámci přípravy",
                text="nakládat s nebezpečnými chemickými látkami.",
            ),
        ]
        parsed = [
            ParsedLegalSection(
                section_type=SECTION_PART,
                section_number="DRUHÁ",
                text="RIZIKOVÉ FAKTORY",
                sort_order=1,
            ),
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="12",
                text="Hodnocení rizik se provádí podle přílohy.",
                sort_order=2,
                parent_sort_order=1,
            ),
        ]
        self.assertFalse(
            legal_section_structure_compare_service.trees_content_equal(
                stored_sections=stored,
                parsed_sections=parsed,
            ),
        )


if __name__ == "__main__":
    unittest.main()
