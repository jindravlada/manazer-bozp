"""SIMILARITY-1: centrální textová podobnost."""

from __future__ import annotations

import unittest

from core.services.text_similarity_service import (
    MATCH_TYPE_EXACT,
    MATCH_TYPE_POSSIBLE,
    MATCH_TYPE_VERY_SIMILAR,
    SimilarityCandidate,
    classify_similarity,
    find_similar_texts,
    normalize_similarity_text,
    similarity_score,
)


class TextSimilarityServiceTestCase(unittest.TestCase):
    def test_exact_match_after_normalization(self) -> None:
        left = normalize_similarity_text("  Dodržujte   předpisy.\n")
        right = normalize_similarity_text("dodržujte předpisy")
        self.assertEqual(left, right)
        self.assertEqual(similarity_score(left, right), 1.0)
        self.assertEqual(classify_similarity(1.0), MATCH_TYPE_EXACT)

    def test_case_difference(self) -> None:
        matches = find_similar_texts(
            "Kontrola OOPP",
            [SimilarityCandidate(id="1", text="kontrola oopp")],
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_type, MATCH_TYPE_EXACT)
        self.assertEqual(matches[0].score_percent, 100)

    def test_extra_whitespace_and_newlines(self) -> None:
        matches = find_similar_texts(
            "Kontrola\nhasicích   přístrojů",
            [SimilarityCandidate(id="a", text="Kontrola hasicích přístrojů")],
        )
        self.assertEqual(matches[0].match_type, MATCH_TYPE_EXACT)

    def test_trailing_punctuation(self) -> None:
        matches = find_similar_texts(
            "Dodržujte bezpečnostní předpisy!!!",
            [SimilarityCandidate(id="a", text="Dodržujte bezpečnostní předpisy")],
        )
        self.assertEqual(matches[0].match_type, MATCH_TYPE_EXACT)

    def test_very_similar_and_possible(self) -> None:
        matches = find_similar_texts(
            "Dodržujte bezpečnostní předpisy",
            [
                SimilarityCandidate(id="near", text="Dodržujte předpisy BOZP"),
                SimilarityCandidate(id="far", text="Úplně jiný text o úniku chemikálií"),
            ],
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].id, "near")
        self.assertIn(matches[0].match_type, {MATCH_TYPE_POSSIBLE, MATCH_TYPE_VERY_SIMILAR})
        self.assertGreaterEqual(matches[0].score, 0.80)
        self.assertLess(matches[0].score, 1.0)

    def test_below_threshold_hidden(self) -> None:
        matches = find_similar_texts(
            "Kontrola únikových cest",
            [SimilarityCandidate(id="x", text="Evidence školení řidičů")],
        )
        self.assertEqual(matches, [])

    def test_exclude_same_record_when_editing(self) -> None:
        matches = find_similar_texts(
            "Kontrola OOPP",
            [
                SimilarityCandidate(id="self", text="Kontrola OOPP"),
                SimilarityCandidate(id="other", text="Kontrola OOPP"),
            ],
            exclude_ids={"self"},
        )
        self.assertEqual([item.id for item in matches], ["other"])

    def test_results_sorted_by_score_desc(self) -> None:
        matches = find_similar_texts(
            "Dodržujte bezpečnostní předpisy na pracovišti",
            [
                SimilarityCandidate(id="low", text="Dodržujte předpisy BOZP"),
                SimilarityCandidate(
                    id="high",
                    text="Dodržujte bezpečnostní předpisy na pracovišti.",
                ),
                SimilarityCandidate(
                    id="mid",
                    text="Dodržujte bezpečnostní předpisy pracoviště",
                ),
            ],
        )
        self.assertGreaterEqual(len(matches), 2)
        scores = [item.score for item in matches]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(matches[0].id, "high")
        self.assertEqual(matches[0].match_type, MATCH_TYPE_EXACT)


if __name__ == "__main__":
    unittest.main()
