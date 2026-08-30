"""SIMILARITY-2: hromadná analýza podobností."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-2-"))
_HOME = _TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_HOME):
    from PySide6.QtWidgets import QApplication, QDialog

    from core.services.text_similarity_service import (
        SimilarityCandidate,
        find_similar_pairs,
    )
    from core.ui.similarity_analysis_dialog import (
        SCOPE_PROVERKY,
        SimilarityAnalysisDialog,
    )
    from moduly.proverky.sluzby.control_point_similarity_analysis import (
        ControlPointSimilarityPair,
        analyze_control_point_similarities,
    )
    from moduly.proverky.sluzby.control_point_similarity_service import (
        ControlPointSimilarityCandidate,
    )


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _candidate(item_id: str, text: str, *, area: str = "a", section: str = "s"):
    return ControlPointSimilarityCandidate(
        composite_id=f"{area}::{section}::{item_id}",
        area_id=area,
        area_name="Oblast",
        section_id=section,
        section_name="Sekce",
        item_id=item_id,
        text=text,
    )


class Similarity2ServiceTestCase(unittest.TestCase):
    def test_find_pairs_and_sort_desc(self) -> None:
        pairs, cancelled = find_similar_pairs(
            [
                SimilarityCandidate("1", "Dodržujte bezpečnostní předpisy"),
                SimilarityCandidate("2", "Dodržujte bezpečnostní předpisy."),
                SimilarityCandidate("3", "Dodržujte předpisy BOZP"),
                SimilarityCandidate("4", "Evidence školení řidičů VZV"),
            ]
        )
        self.assertFalse(cancelled)
        self.assertGreaterEqual(len(pairs), 2)
        scores = [item.score for item in pairs]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(pairs[0].score_percent, 100)
        ids = {(item.left_id, item.right_id) for item in pairs}
        self.assertIn(("1", "2"), ids)

    def test_cancel_stops_analysis(self) -> None:
        cancel = {"flag": False}

        def should_cancel():
            return cancel["flag"]

        def on_progress(current, total, found):
            if current >= 1:
                cancel["flag"] = True

        pairs, cancelled = find_similar_pairs(
            [
                SimilarityCandidate(str(i), f"Kontrola OOPP varianta {i}")
                for i in range(20)
            ],
            progress_callback=on_progress,
            should_cancel=should_cancel,
        )
        self.assertTrue(cancelled)

    def test_analyze_control_points_uses_locations(self) -> None:
        catalog = [
            _candidate("a1", "Kontrola hasicích přístrojů"),
            _candidate("a2", "Kontrola hasicích přístrojů."),
            _candidate("b1", "Úplně jiný text o chemii"),
        ]
        with patch(
            "moduly.proverky.sluzby.control_point_similarity_analysis.collect_control_point_candidates",
            return_value=catalog,
        ):
            pairs, cancelled = analyze_control_point_similarities()
        self.assertFalse(cancelled)
        self.assertEqual(len(pairs), 1)
        self.assertIsInstance(pairs[0], ControlPointSimilarityPair)
        self.assertIn("Prověrky BOZP", pairs[0].left.location_label)
        self.assertIn("Oblast", pairs[0].left.location_label)
        self.assertIn("Sekce", pairs[0].right.location_label)
        self.assertEqual(pairs[0].score_percent, 100)

    def test_empty_result(self) -> None:
        with patch(
            "moduly.proverky.sluzby.control_point_similarity_analysis.collect_control_point_candidates",
            return_value=[
                _candidate("x", "Alpha unikátní text"),
                _candidate("y", "Beta úplně jiné znění"),
            ],
        ):
            pairs, cancelled = analyze_control_point_similarities()
        self.assertFalse(cancelled)
        self.assertEqual(pairs, [])


class Similarity2UiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_dialog_has_two_scope_combos(self) -> None:
        dialog = SimilarityAnalysisDialog()
        self.assertEqual(dialog._selected_scope_a(), SCOPE_PROVERKY)
        self.assertEqual(dialog._selected_scope_b(), SCOPE_PROVERKY)
        self.assertGreaterEqual(dialog._scope_a_combo.count(), 6)
        self.assertEqual(dialog._scope_a_combo.count(), dialog._scope_b_combo.count())

    def test_empty_results_page(self) -> None:
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = []
        dialog._cancelled = False
        dialog._show_results()
        self.assertFalse(dialog._empty_label.isHidden())
        self.assertTrue(dialog._results_table.isHidden())
        self.assertIn("Celkem nalezeno: 0", dialog._results_counts.text())
        self.assertIn("Analýza dokončena", dialog._results_summary.text())

    def test_results_show_location_and_sorted_pairs(self) -> None:
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [
            ControlPointSimilarityPair(
                score=1.0,
                match_type="exact",
                match_label="Přesná shoda",
                left=_candidate("1", "Kontrola OOPP"),
                right=_candidate("2", "Kontrola OOPP."),
            ),
            ControlPointSimilarityPair(
                score=0.85,
                match_type="possible",
                match_label="Možná podobnost",
                left=_candidate("3", "Dodržujte bezpečnostní předpisy"),
                right=_candidate("4", "Dodržujte předpisy BOZP"),
            ),
        ]
        dialog._cancelled = False
        dialog._show_results()
        self.assertEqual(dialog._results_table.rowCount(), 2)
        self.assertIn("100 %", dialog._results_table.item(0, 1).text())
        self.assertEqual(
            dialog._results_table.item(0, 4).text(),
            "Oblast → Sekce",
        )
        self.assertEqual(
            dialog._results_table.item(0, 6).text(),
            "Oblast → Sekce",
        )
        self.assertIn("Prověrky BOZP", dialog._results_table.item(0, 4).toolTip())
        self.assertIn("Prověrky BOZP", dialog._pairs[0].left.location_label)


if __name__ == "__main__":
    unittest.main()
