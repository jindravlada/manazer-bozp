"""CONTROL-REPORT-CZECH-SENTENCES-2: klauzule ženského rodu podle počtu."""

from __future__ import annotations

import unittest

from core.shared.sluzby.control_report_language import (
    NESHODA_FORMS,
    PRILEZITOST_FORMS,
    ZAVADA_FORMS,
    format_during_found_sentence,
    format_feminine_found_clause,
    join_found_clauses,
)
from core.utils.czech_count import CzechCountForm, czech_count_form


_COUNTS = (0, 1, 2, 3, 4, 5, 11, 21, 22, 25, 101)

_NOUNS = (
    ("závada", ZAVADA_FORMS),
    ("neshoda", NESHODA_FORMS),
    ("příležitost ke zlepšení", PRILEZITOST_FORMS),
)

_VERBS = {
    CzechCountForm.ONE: "byla zjištěna",
    CzechCountForm.FEW: "byly zjištěny",
    CzechCountForm.MANY: "bylo zjištěno",
}


class ControlReportLanguageTestCase(unittest.TestCase):
    def test_feminine_found_clause_for_report_counts(self) -> None:
        for label, forms in _NOUNS:
            for count in _COUNTS:
                with self.subTest(count=count, noun=label):
                    form = czech_count_form(count)
                    expected = (
                        f"{_VERBS[form]} {count} {forms[form.value]}"
                    )
                    self.assertEqual(
                        expected,
                        format_feminine_found_clause(count, **forms),
                    )

    def test_exact_clauses_from_spec(self) -> None:
        self.assertEqual(
            "byla zjištěna 1 závada",
            format_feminine_found_clause(1, **ZAVADA_FORMS),
        )
        self.assertEqual(
            "byly zjištěny 3 neshody",
            format_feminine_found_clause(3, **NESHODA_FORMS),
        )
        self.assertEqual(
            "bylo zjištěno 5 příležitostí ke zlepšení",
            format_feminine_found_clause(5, **PRILEZITOST_FORMS),
        )
        self.assertEqual(
            "bylo zjištěno 21 příležitostí ke zlepšení",
            format_feminine_found_clause(21, **PRILEZITOST_FORMS),
        )
        self.assertEqual(
            "bylo zjištěno 22 příležitostí ke zlepšení",
            format_feminine_found_clause(22, **PRILEZITOST_FORMS),
        )
        self.assertEqual(
            "bylo zjištěno 101 neshod",
            format_feminine_found_clause(101, **NESHODA_FORMS),
        )

    def test_join_one_or_two_clauses(self) -> None:
        one = format_feminine_found_clause(1, **ZAVADA_FORMS)
        five = format_feminine_found_clause(5, **PRILEZITOST_FORMS)
        self.assertEqual(one, join_found_clauses([one]))
        self.assertEqual(
            "byla zjištěna 1 závada a bylo zjištěno 5 příležitostí ke zlepšení",
            join_found_clauses([one, five]),
        )

    def test_during_sentence_single_and_combined(self) -> None:
        self.assertEqual(
            "Během prověrky bylo zjištěno 5 příležitostí ke zlepšení.",
            format_during_found_sentence(
                during="Během prověrky",
                clauses=[format_feminine_found_clause(5, **PRILEZITOST_FORMS)],
                empty="Během prověrky nebyla zjištěna významná zjištění.",
            ),
        )
        self.assertEqual(
            "Během auditu byly zjištěny 3 neshody.",
            format_during_found_sentence(
                during="Během auditu",
                clauses=[format_feminine_found_clause(3, **NESHODA_FORMS)],
                empty="Během auditu nebyla zjištěna významná zjištění.",
            ),
        )
        self.assertEqual(
            "Během prověrky byla zjištěna 1 závada a bylo zjištěno 5 příležitostí ke zlepšení.",
            format_during_found_sentence(
                during="Během prověrky",
                clauses=[
                    format_feminine_found_clause(1, **ZAVADA_FORMS),
                    format_feminine_found_clause(5, **PRILEZITOST_FORMS),
                ],
                empty="Během prověrky nebyla zjištěna významná zjištění.",
            ),
        )
        self.assertEqual(
            "Během auditu byly zjištěny 2 neshody a byla zjištěna 1 příležitost ke zlepšení.",
            format_during_found_sentence(
                during="Během auditu",
                clauses=[
                    format_feminine_found_clause(2, **NESHODA_FORMS),
                    format_feminine_found_clause(1, **PRILEZITOST_FORMS),
                ],
                empty="Během auditu nebyla zjištěna významná zjištění.",
            ),
        )

    def test_during_sentence_empty_keeps_current_zero_wording(self) -> None:
        empty = "Během prověrky nebyla zjištěna významná zjištění."
        self.assertEqual(
            empty,
            format_during_found_sentence(
                during="Během prověrky",
                clauses=[],
                empty=empty,
            ),
        )
        self.assertNotIn("bylo zjištěno 0", empty)


if __name__ == "__main__":
    unittest.main()
