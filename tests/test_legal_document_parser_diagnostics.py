import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from moduly.pravni_pozadavky.parser.legal_document_parser import legal_document_parser
from moduly.pravni_pozadavky.parser.legal_document_parser_diagnostics import (
    LegalDocumentParserDiagnostics,
    legal_document_parser_diagnostics,
)
from moduly.pravni_pozadavky.parser.legal_document_parser_models import (
    LegalDocumentParseResult,
    ParsedLegalSection,
    SECTION_DIVISION,
    SECTION_HEAD,
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_PART,
    SECTION_SUBSECTION,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_HIERARCHY_PATH = PROJECT_ROOT / "tests" / "data" / "sample_hierarchie_predpisu.txt"
CLI_PATH = PROJECT_ROOT / "tools" / "parse_legal_document.py"


class LegalDocumentParserDiagnosticsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.diagnostics = LegalDocumentParserDiagnostics()
        self.sample_text = SAMPLE_HIERARCHY_PATH.read_text(encoding="utf-8")
        self.parse_result = legal_document_parser.parse_text(
            self.sample_text,
            document_type="zakon",
            number="1",
            year=2026,
            title="Testovací předpis",
        )

    def test_analyze_returns_counts_by_type(self) -> None:
        result = self.diagnostics.analyze(self.parse_result)

        self.assertEqual(result.total_sections, 7)
        self.assertEqual(result.counts_by_type[SECTION_PART], 1)
        self.assertEqual(result.counts_by_type[SECTION_HEAD], 1)
        self.assertEqual(result.counts_by_type[SECTION_DIVISION], 1)
        self.assertEqual(result.counts_by_type[SECTION_PARAGRAPH], 1)
        self.assertEqual(result.counts_by_type[SECTION_SUBSECTION], 1)
        self.assertEqual(result.counts_by_type[SECTION_LETTER], 2)
        self.assertGreater(result.max_depth, 0)

    def test_valid_hierarchy_has_hierarchy_ok_true(self) -> None:
        result = self.diagnostics.analyze(self.parse_result)

        self.assertTrue(result.hierarchy_ok)
        self.assertEqual(result.missing_parent_count, 0)
        self.assertEqual(result.invalid_parent_count, 0)
        self.assertEqual(len(result.errors), 0)

    def test_invalid_hierarchy_returns_error(self) -> None:
        invalid_result = LegalDocumentParseResult(
            sections=[
                ParsedLegalSection(
                    section_type=SECTION_PART,
                    section_number="PRVNÍ",
                    sort_order=1,
                ),
                ParsedLegalSection(
                    section_type=SECTION_PARAGRAPH,
                    paragraph="1",
                    sort_order=2,
                    parent_sort_order=1,
                ),
                ParsedLegalSection(
                    section_type=SECTION_LETTER,
                    item_letter="a",
                    sort_order=3,
                    parent_sort_order=2,
                ),
            ],
        )

        result = self.diagnostics.analyze(invalid_result)

        self.assertFalse(result.hierarchy_ok)
        self.assertEqual(result.invalid_parent_count, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].sort_order, 3)
        self.assertEqual(result.errors[0].section_type, SECTION_LETTER)
        self.assertIn("Neplatný rodič", result.errors[0].message)

    def test_export_tree_creates_txt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "strom.txt"
            legal_document_parser_diagnostics.export_tree(self.parse_result, output_path)

            self.assertTrue(output_path.is_file())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("ČÁST PRVNÍ", content)
            self.assertIn("  HLAVA I", content)
            self.assertIn("    DÍL 1", content)
            self.assertIn("      § 1 Tento zákon", content)
            self.assertIn("        odst. 1", content)
            self.assertIn("          písm. a)", content)
            self.assertIn("          písm. b)", content)

    def test_cli_runs_on_sample_txt(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(CLI_PATH),
                str(SAMPLE_HIERARCHY_PATH),
                "--title",
                "Testovací předpis",
                "--type",
                "Zákon",
                "--number",
                "1",
                "--year",
                "2026",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Počet všech částí: 7", completed.stdout)
        self.assertIn("hierarchy_ok: Ano", completed.stdout)

    def test_cli_prints_hierarchy_errors_for_invalid_txt(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as handle:
            handle.write("§ 1\nNadpis\na) písmeno bez odstavce\n")
            invalid_path = handle.name

        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    invalid_path,
                    "--title",
                    "Neplatný předpis",
                    "--type",
                    "Zákon",
                    "--number",
                    "1",
                    "--year",
                    "2026",
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            Path(invalid_path).unlink(missing_ok=True)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("hierarchy_ok: Ne", completed.stdout)
        self.assertIn("Celkový počet chyb hierarchie: 2", completed.stdout)
        self.assertIn("Prvních 2 chyb hierarchie:", completed.stdout)
        self.assertIn("section_type=pismeno", completed.stdout)
        self.assertIn("parent_sort_order=1", completed.stdout)
        self.assertIn("Neplatný rodič", completed.stdout)


if __name__ == "__main__":
    unittest.main()
