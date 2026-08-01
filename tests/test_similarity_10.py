"""SIMILARITY-10: obecná analýza podobností mezi dvěma oblastmi."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-10-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtWidgets import QApplication, QMessageBox

    from core.database.database_initializer import initialize_database
    from core.services.text_similarity_service import (
        SimilarityCandidate,
        find_similar_pairs,
        find_similar_pairs_between,
    )
    from core.shared.sluzby.similarity_domain import (
        SCOPE_AUDIT,
        SCOPE_LEGAL,
        SCOPE_MEASURES,
        SCOPE_PBP,
        SCOPE_PROVERKY,
        SCOPE_RISKS,
        SIMILARITY_DOMAINS,
        SIMILARITY_LARGE_ANALYSIS_THRESHOLD,
        estimate_comparison_count,
        estimate_duration_label,
        requires_large_analysis_confirmation,
    )
    from core.shared.sluzby.similarity_domain_analysis import (
        SimilarityAnalysisPair,
        analyze_domain_similarities,
    )
    from core.shared.sluzby.similarity_item_collectors import SimilarityItem
    from core.ui.similarity_analysis_dialog import SimilarityAnalysisDialog

    initialize_database()


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _item(entity: str, item_id: str, text: str) -> SimilarityItem:
    return SimilarityItem(
        entity_type=entity,
        composite_id=item_id,
        text=text,
        location_label=f"Loc {item_id}",
    )


class Similarity10EstimateTestCase(unittest.TestCase):
    def test_same_domain_comparison_count(self) -> None:
        self.assertEqual(estimate_comparison_count(5, 5, same_domain=True), 10)
        self.assertEqual(estimate_comparison_count(1, 1, same_domain=True), 0)
        self.assertEqual(estimate_comparison_count(0, 0, same_domain=True), 0)

    def test_cross_domain_comparison_count(self) -> None:
        self.assertEqual(estimate_comparison_count(3, 4, same_domain=False), 12)

    def test_duration_label_scales(self) -> None:
        self.assertEqual(estimate_duration_label(100), "≈ několik sekund")
        self.assertEqual(estimate_duration_label(100_000), "≈ do 1 minuty")
        self.assertEqual(estimate_duration_label(1_000_000), "≈ 2–5 minut")
        self.assertEqual(estimate_duration_label(20_000_000), "≈ více než 5 minut")

    def test_large_analysis_threshold(self) -> None:
        self.assertFalse(
            requires_large_analysis_confirmation(SIMILARITY_LARGE_ANALYSIS_THRESHOLD)
        )
        self.assertTrue(
            requires_large_analysis_confirmation(
                SIMILARITY_LARGE_ANALYSIS_THRESHOLD + 1
            )
        )


class Similarity10CrossPairsTestCase(unittest.TestCase):
    def test_find_similar_pairs_between_uses_same_scoring(self) -> None:
        left = [SimilarityCandidate(id="a1", text="Kontrola hasicích přístrojů")]
        right = [
            SimilarityCandidate(id="b1", text="Kontrola hasicích přístrojů."),
            SimilarityCandidate(id="b2", text="Úplně jiný text bez podobnosti xyz"),
        ]
        pairs, cancelled = find_similar_pairs_between(left, right)
        self.assertFalse(cancelled)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].left_id, "a1")
        self.assertEqual(pairs[0].right_id, "b1")

    def test_same_list_pair_count_matches_estimate(self) -> None:
        items = [
            SimilarityCandidate(id=str(i), text=f"Text číslo {i} varianta")
            for i in range(6)
        ]
        # Vynutíme shody přesné duplicitou.
        items[1] = SimilarityCandidate(id="1", text=items[0].text)
        items[3] = SimilarityCandidate(id="3", text=items[2].text)
        estimate = estimate_comparison_count(len(items), len(items), same_domain=True)
        pairs, _ = find_similar_pairs(items)
        # Odhad = všechny dvojice; nalezené páry ≤ odhad.
        self.assertEqual(estimate, 15)
        self.assertLessEqual(len(pairs), estimate)
        self.assertGreaterEqual(len(pairs), 2)


class Similarity10AnalysisTestCase(unittest.TestCase):
    def test_analyze_same_domain(self) -> None:
        catalog = [
            _item("t", "1", "Stejný bezpečnostní text"),
            _item("t", "2", "Stejný bezpečnostní text."),
            _item("t", "3", "Úplně odlišný obsah qwerty"),
        ]
        with patch(
            "core.shared.sluzby.similarity_domain_analysis.collect_similarity_items",
            return_value=catalog,
        ):
            pairs, cancelled = analyze_domain_similarities(
                SCOPE_PROVERKY, SCOPE_PROVERKY
            )
        self.assertFalse(cancelled)
        self.assertGreaterEqual(len(pairs), 1)
        self.assertTrue(all(isinstance(p, SimilarityAnalysisPair) for p in pairs))

    def test_analyze_cross_domain(self) -> None:
        left = [_item("proverky_kontrolni_otazka", "1", "Kontrola OOPP na pracovišti")]
        right = [
            _item("pravni_pozadavek", "9", "Kontrola OOPP na pracovišti."),
            _item("pravni_pozadavek", "8", "Něco zcela jiného abcdef"),
        ]

        def fake_collect(scope_key, *, include_inactive=True):
            if scope_key == SCOPE_PROVERKY:
                return left
            if scope_key == SCOPE_LEGAL:
                return right
            return []

        with patch(
            "core.shared.sluzby.similarity_domain_analysis.collect_similarity_items",
            side_effect=fake_collect,
        ):
            pairs, cancelled = analyze_domain_similarities(
                SCOPE_PROVERKY, SCOPE_LEGAL
            )
        self.assertFalse(cancelled)
        self.assertEqual(len(pairs), 1)
        self.assertIn("cross:", pairs[0].pair_entity_type)


class Similarity10UiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_all_domains_selectable(self) -> None:
        dialog = SimilarityAnalysisDialog()
        labels_a = [
            dialog._scope_a_combo.itemText(i)
            for i in range(dialog._scope_a_combo.count())
        ]
        labels_b = [
            dialog._scope_b_combo.itemText(i)
            for i in range(dialog._scope_b_combo.count())
        ]
        expected = [d.label for d in SIMILARITY_DOMAINS]
        self.assertEqual(labels_a, expected)
        self.assertEqual(labels_b, expected)
        keys = {d.key for d in SIMILARITY_DOMAINS}
        self.assertEqual(
            keys,
            {
                SCOPE_PROVERKY,
                SCOPE_PBP,
                SCOPE_AUDIT,
                SCOPE_RISKS,
                SCOPE_MEASURES,
                SCOPE_LEGAL,
            },
        )

    def test_estimate_updates_for_same_and_cross(self) -> None:
        dialog = SimilarityAnalysisDialog()

        def fake_collect(scope_key, *, include_inactive=True):
            if scope_key == SCOPE_PROVERKY:
                return [_item("p", str(i), f"t{i}") for i in range(4)]
            if scope_key == SCOPE_LEGAL:
                return [_item("l", str(i), f"l{i}") for i in range(3)]
            return []

        with patch(
            "core.ui.similarity_analysis_dialog.collect_similarity_items",
            side_effect=fake_collect,
        ):
            dialog._scope_a_combo.setCurrentIndex(
                next(
                    i
                    for i in range(dialog._scope_a_combo.count())
                    if dialog._scope_a_combo.itemData(i) == SCOPE_PROVERKY
                )
            )
            dialog._scope_b_combo.setCurrentIndex(
                next(
                    i
                    for i in range(dialog._scope_b_combo.count())
                    if dialog._scope_b_combo.itemData(i) == SCOPE_PROVERKY
                )
            )
            dialog._refresh_scope_estimates()
            self.assertEqual(dialog._count_a, 4)
            self.assertEqual(dialog._count_b, 4)
            self.assertEqual(dialog._comparison_estimate, 6)
            self.assertIn("6", dialog._estimate_label.text())

            dialog._scope_b_combo.setCurrentIndex(
                next(
                    i
                    for i in range(dialog._scope_b_combo.count())
                    if dialog._scope_b_combo.itemData(i) == SCOPE_LEGAL
                )
            )
            dialog._refresh_scope_estimates()
            self.assertEqual(dialog._comparison_estimate, 12)
            self.assertIn("12", dialog._estimate_label.text())

    def test_large_analysis_shows_confirmation(self) -> None:
        dialog = SimilarityAnalysisDialog()
        dialog._comparison_estimate = SIMILARITY_LARGE_ANALYSIS_THRESHOLD + 1
        dialog._count_a = 1
        dialog._count_b = 1

        with patch.object(dialog, "_refresh_scope_estimates"), patch(
            "core.ui.similarity_analysis_dialog.requires_large_analysis_confirmation",
            return_value=True,
        ), patch(
            "core.ui.similarity_analysis_dialog.QMessageBox"
        ) as msg_cls, patch(
            "core.ui.similarity_analysis_dialog.analyze_domain_similarities",
            return_value=([], False),
        ):
            box = msg_cls.return_value
            cancel_btn = object()
            continue_btn = object()
            box.addButton.side_effect = [continue_btn, cancel_btn]
            box.clickedButton.return_value = cancel_btn
            dialog._start_analysis()
            self.assertIsNone(dialog._worker)
            box.setDefaultButton.assert_called()

    def test_results_dialog_unchanged_for_pairs(self) -> None:
        dialog = SimilarityAnalysisDialog()
        pair = SimilarityAnalysisPair(
            score=1.0,
            match_type="exact",
            match_label="Přesná shoda",
            left=_item("proverky_kontrolni_otazka", "a::s::1", "Text A"),
            right=_item("proverky_kontrolni_otazka", "a::s::2", "Text A."),
            checked=False,
            pair_entity_type="proverky_kontrolni_otazka",
        )
        dialog._pairs = [pair]
        dialog._show_results()
        self.assertEqual(dialog._results_table.rowCount(), 1)
        self.assertIn("100 %", dialog._results_table.item(0, 1).text())
        self.assertEqual(dialog._results_table.item(0, 3).text(), "Text A")


if __name__ == "__main__":
    unittest.main()
