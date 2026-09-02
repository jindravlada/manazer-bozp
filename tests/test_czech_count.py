"""CONTROL-REPORT-CZECH-COUNT-1: české tvary podle číselně zapsaného počtu."""

from __future__ import annotations

import unittest

from core.utils.czech_count import CzechCountForm, czech_count_form, format_czech_count


_NOUNS = (
    ("příležitost", "příležitosti", "příležitostí"),
    ("závada", "závady", "závad"),
    ("neshoda", "neshody", "neshod"),
    ("úkol", "úkoly", "úkolů"),
    ("zjištění", "zjištění", "zjištění"),
)

_COUNTS = (0, 1, 2, 3, 4, 5, 11, 21, 22, 25, 101)

_EXPECTED_FORMS = {
    0: CzechCountForm.MANY,
    1: CzechCountForm.ONE,
    2: CzechCountForm.FEW,
    3: CzechCountForm.FEW,
    4: CzechCountForm.FEW,
    5: CzechCountForm.MANY,
    11: CzechCountForm.MANY,
    21: CzechCountForm.MANY,
    22: CzechCountForm.MANY,
    25: CzechCountForm.MANY,
    101: CzechCountForm.MANY,
}


class CzechCountTestCase(unittest.TestCase):
    def test_form_uses_whole_number_not_last_digit(self) -> None:
        for count in _COUNTS:
            with self.subTest(count=count):
                self.assertIs(_EXPECTED_FORMS[count], czech_count_form(count))

    def test_format_nouns_for_report_counts(self) -> None:
        for one, few, many in _NOUNS:
            expected_word = {
                CzechCountForm.ONE: one,
                CzechCountForm.FEW: few,
                CzechCountForm.MANY: many,
            }
            for count in _COUNTS:
                with self.subTest(count=count, one=one):
                    self.assertEqual(
                        f"{count} {expected_word[_EXPECTED_FORMS[count]]}",
                        format_czech_count(count, one=one, few=few, many=many),
                    )

    def test_format_strips_word_forms(self) -> None:
        self.assertEqual(
            "5 příležitostí",
            format_czech_count(
                5,
                one="  příležitost  ",
                few=" příležitosti ",
                many=" příležitostí\n",
            ),
        )

    def test_rejects_invalid_count(self) -> None:
        invalid = (-1, -5, 1.0, 1.5, "1", None, True, False)
        for value in invalid:
            with self.subTest(count=value):
                with self.assertRaises((TypeError, ValueError)) as ctx:
                    czech_count_form(value)  # type: ignore[arg-type]
                self.assertEqual(
                    "count musí být nezáporné celé číslo.",
                    str(ctx.exception),
                )

    def test_rejects_empty_word_forms(self) -> None:
        cases = (
            {"one": "", "few": "příležitosti", "many": "příležitostí", "name": "one"},
            {"one": "   ", "few": "příležitosti", "many": "příležitostí", "name": "one"},
            {"one": "příležitost", "few": "", "many": "příležitostí", "name": "few"},
            {"one": "příležitost", "few": "  ", "many": "příležitostí", "name": "few"},
            {"one": "příležitost", "few": "příležitosti", "many": "", "name": "many"},
            {"one": "příležitost", "few": "příležitosti", "many": "\n", "name": "many"},
            {"one": None, "few": "příležitosti", "many": "příležitostí", "name": "one"},
        )
        for case in cases:
            with self.subTest(name=case["name"], value=case[case["name"]]):
                with self.assertRaises((TypeError, ValueError)) as ctx:
                    format_czech_count(
                        1,
                        one=case["one"],  # type: ignore[arg-type]
                        few=case["few"],
                        many=case["many"],
                    )
                self.assertEqual(
                    f"tvar {case['name']} musí být neprázdný řetězec.",
                    str(ctx.exception),
                )


if __name__ == "__main__":
    unittest.main()
