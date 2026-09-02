"""CONTROL-REPORT-FINDINGS-SUMMARY-7: helper rozpisu Finding podle druhu."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.shared.constants import (
    FINDING_TYPE_NEDOSTATEK,
    FINDING_TYPE_NESHODA,
    FINDING_TYPE_POKYN,
    FINDING_TYPE_POZOROVANI,
    FINDING_TYPE_PRILEZITOST,
    FINDING_TYPE_ZAVADA,
    FINDING_TYPE_ZJISTENI,
)
from core.shared.sluzby.control_report_findings_summary import (
    FINDINGS_TOTAL_OVERVIEW_LABEL,
    OTHER_FINDINGS_OVERVIEW_LABEL,
    count_findings_by_type,
    format_audit_evidence_sentence,
    format_findings_overview_lines,
    format_inspection_evidence_sentence,
    join_czech_enumerated,
)
from core.shared.sluzby.control_report_language import (
    AUDIT_EMPTY_FOUND_SENTENCE,
    INSPECTION_EMPTY_FOUND_SENTENCE,
)
from moduly.audity.constants import AUDIT_FINDING_REPORT_TYPE_ORDER
from moduly.proverky.constants import INSPECTION_FINDING_REPORT_TYPE_ORDER


def _f(finding_type: str) -> SimpleNamespace:
    return SimpleNamespace(finding_type=finding_type)


class ControlReportFindingsSummaryHelperTestCase(unittest.TestCase):
    def test_empty_sentences(self) -> None:
        self.assertEqual(
            INSPECTION_EMPTY_FOUND_SENTENCE,
            format_inspection_evidence_sentence([], INSPECTION_FINDING_REPORT_TYPE_ORDER),
        )
        self.assertEqual(
            AUDIT_EMPTY_FOUND_SENTENCE,
            format_audit_evidence_sentence([], AUDIT_FINDING_REPORT_TYPE_ORDER),
        )
        self.assertEqual(
            "Evidence prověrky neobsahuje žádná zjištění.",
            INSPECTION_EMPTY_FOUND_SENTENCE,
        )
        self.assertEqual(
            "Evidence auditu neobsahuje žádná zjištění.",
            AUDIT_EMPTY_FOUND_SENTENCE,
        )

    def test_one_pkz_inspection(self) -> None:
        findings = [_f(FINDING_TYPE_PRILEZITOST)]
        self.assertEqual(
            "Evidence prověrky obsahuje 1 zjištění, z toho 1 příležitost ke zlepšení.",
            format_inspection_evidence_sentence(
                findings, INSPECTION_FINDING_REPORT_TYPE_ORDER
            ),
        )

    def test_few_same_type(self) -> None:
        findings = [_f(FINDING_TYPE_ZAVADA)] * 3
        self.assertEqual(
            "Evidence prověrky obsahuje 3 zjištění, z toho 3 závady.",
            format_inspection_evidence_sentence(
                findings, INSPECTION_FINDING_REPORT_TYPE_ORDER
            ),
        )

    def test_five_pkz(self) -> None:
        findings = [_f(FINDING_TYPE_PRILEZITOST)] * 5
        self.assertEqual(
            "Evidence prověrky obsahuje 5 zjištění, z toho 5 příležitostí ke zlepšení.",
            format_inspection_evidence_sentence(
                findings, INSPECTION_FINDING_REPORT_TYPE_ORDER
            ),
        )

    def test_mixed_inspection_example(self) -> None:
        findings = (
            [_f(FINDING_TYPE_ZAVADA)]
            + [_f(FINDING_TYPE_NEDOSTATEK)]
            + [_f(FINDING_TYPE_PRILEZITOST)] * 5
        )
        self.assertEqual(
            "Evidence prověrky obsahuje 7 zjištění, z toho 1 závadu, "
            "1 nedostatek a 5 příležitostí ke zlepšení.",
            format_inspection_evidence_sentence(
                findings, INSPECTION_FINDING_REPORT_TYPE_ORDER
            ),
        )

    def test_mixed_audit_example(self) -> None:
        findings = [_f(FINDING_TYPE_NESHODA)] * 2 + [_f(FINDING_TYPE_PRILEZITOST)]
        self.assertEqual(
            "Evidence auditu obsahuje 3 zjištění, z toho 2 neshody a "
            "1 příležitost ke zlepšení.",
            format_audit_evidence_sentence(findings, AUDIT_FINDING_REPORT_TYPE_ORDER),
        )

    def test_audit_observation_before_pkz(self) -> None:
        findings = [
            _f(FINDING_TYPE_PRILEZITOST),
            _f(FINDING_TYPE_POZOROVANI),
            _f(FINDING_TYPE_NESHODA),
        ]
        sentence = format_audit_evidence_sentence(
            findings, AUDIT_FINDING_REPORT_TYPE_ORDER
        )
        self.assertEqual(
            "Evidence auditu obsahuje 3 zjištění, z toho 1 neshodu, "
            "1 pozorování a 1 příležitost ke zlepšení.",
            sentence,
        )
        neshoda = sentence.find("neshodu")
        pozorovani = sentence.find("pozorování")
        pkz = sentence.find("příležitost")
        self.assertLess(neshoda, pozorovani)
        self.assertLess(pozorovani, pkz)

    def test_inspection_order_stable_regardless_of_input(self) -> None:
        findings = [
            _f(FINDING_TYPE_PRILEZITOST),
            _f(FINDING_TYPE_ZJISTENI),
            _f(FINDING_TYPE_ZAVADA),
        ]
        lines = format_findings_overview_lines(
            findings, INSPECTION_FINDING_REPORT_TYPE_ORDER
        )
        self.assertEqual(
            [
                "Zjištění celkem: 3",
                "Závady: 1",
                "Zjištění: 1",
                "Příležitosti ke zlepšení: 1",
            ],
            lines,
        )

    def test_unknown_type_goes_to_other_and_stays_in_total(self) -> None:
        findings = [_f(FINDING_TYPE_ZAVADA), _f(FINDING_TYPE_POKYN), _f("historicky_xyz")]
        breakdown = count_findings_by_type(
            findings, INSPECTION_FINDING_REPORT_TYPE_ORDER
        )
        self.assertEqual(3, breakdown.total)
        self.assertEqual(3, breakdown.parts_sum())
        self.assertEqual(2, breakdown.other_count)
        lines = format_findings_overview_lines(
            findings, INSPECTION_FINDING_REPORT_TYPE_ORDER
        )
        self.assertEqual(
            [
                "Zjištění celkem: 3",
                "Závady: 1",
                "Ostatní zjištění: 2",
            ],
            lines,
        )
        sentence = format_inspection_evidence_sentence(
            findings, INSPECTION_FINDING_REPORT_TYPE_ORDER
        )
        self.assertIn("3 zjištění", sentence)
        self.assertIn("1 závadu", sentence)
        self.assertIn("2 ostatní zjištění", sentence)

    def test_audit_unknown_type_is_other(self) -> None:
        findings = [_f(FINDING_TYPE_NESHODA), _f(FINDING_TYPE_ZAVADA)]
        lines = format_findings_overview_lines(
            findings, AUDIT_FINDING_REPORT_TYPE_ORDER
        )
        self.assertEqual(
            [
                "Zjištění celkem: 2",
                "Neshody: 1",
                "Ostatní zjištění: 1",
            ],
            lines,
        )

    def test_overview_zero_still_shows_total(self) -> None:
        lines = format_findings_overview_lines([], INSPECTION_FINDING_REPORT_TYPE_ORDER)
        self.assertEqual([f"{FINDINGS_TOTAL_OVERVIEW_LABEL}: 0"], lines)
        self.assertNotIn(OTHER_FINDINGS_OVERVIEW_LABEL, "\n".join(lines))

    def test_join_three_parts(self) -> None:
        self.assertEqual("A, B a C", join_czech_enumerated(["A", "B", "C"]))
        self.assertEqual("A a B", join_czech_enumerated(["A", "B"]))

    def test_contains_does_not_inflect(self) -> None:
        one = format_inspection_evidence_sentence(
            [_f(FINDING_TYPE_ZAVADA)], INSPECTION_FINDING_REPORT_TYPE_ORDER
        )
        five = format_inspection_evidence_sentence(
            [_f(FINDING_TYPE_ZAVADA)] * 5, INSPECTION_FINDING_REPORT_TYPE_ORDER
        )
        self.assertTrue(one.startswith("Evidence prověrky obsahuje "))
        self.assertTrue(five.startswith("Evidence prověrky obsahuje "))
        self.assertNotIn("obsahují", one)
        self.assertNotIn("obsahují", five)


if __name__ == "__main__":
    unittest.main()
