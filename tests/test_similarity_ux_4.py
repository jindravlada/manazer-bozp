"""SIMILARITY-UX-4: hromadné označení falešných duplicit."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-ux-4-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from core.database.database_initializer import initialize_database
    from core.database.session import get_session
    from core.shared.modely.similarity_checked_pair import SimilarityCheckedPair
    from core.shared.sluzby.similarity_checked_pair_service import (
        SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
        similarity_checked_pair_service,
    )
    from core.ui.similarity_analysis_dialog import (
        SimilarityAnalysisDialog,
        _COL_SELECT,
    )
    from moduly.proverky.sluzby.control_point_similarity_analysis import (
        ControlPointSimilarityPair,
        analyze_control_point_similarities,
    )
    from moduly.proverky.sluzby.control_point_similarity_service import (
        ControlPointSimilarityCandidate,
    )

    initialize_database()


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _candidate(item_id: str, text: str) -> ControlPointSimilarityCandidate:
    return ControlPointSimilarityCandidate(
        composite_id=f"area::sekce::{item_id}",
        area_id="area",
        area_name="Oblast",
        section_id="sekce",
        section_name="Sekce",
        item_id=item_id,
        text=text,
    )


def _pair(left_id: str, right_id: str, score: float = 0.9) -> ControlPointSimilarityPair:
    return ControlPointSimilarityPair(
        score=score,
        match_type="possible",
        match_label="Možná podobnost",
        left=_candidate(left_id, f"Otázka {left_id}"),
        right=_candidate(right_id, f"Otázka {right_id}"),
    )


class SimilarityUx4BulkMarkTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with get_session() as session:
            session.query(SimilarityCheckedPair).delete()
            session.commit()

    def test_can_check_arbitrary_pairs(self) -> None:
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [_pair("1", "2"), _pair("3", "4"), _pair("5", "6")]
        dialog._show_results()

        self.assertIn("Zaškrtněte dvojice", dialog._bulk_hint.text())
        self.assertEqual(dialog._bulk_mark_btn.text(), "Označit vybrané jako zkontrolované")

        for row in (0, 2):
            item = dialog._results_table.item(row, _COL_SELECT)
            self.assertTrue(item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)

        self.assertEqual(dialog._selected_row_indexes(), [0, 2])
        self.assertIn("Celkem nalezeno: 3", dialog._results_counts.text())
        self.assertIn("Vybráno: 2", dialog._results_counts.text())
        self.assertIn("Zbývá k posouzení: 1", dialog._results_counts.text())
        self.assertTrue(dialog._bulk_mark_btn.isEnabled())

    def test_bulk_mark_persists_and_removes_rows(self) -> None:
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [_pair("1", "2"), _pair("3", "4"), _pair("5", "6")]
        dialog._show_results()

        dialog._results_table.item(0, _COL_SELECT).setCheckState(Qt.CheckState.Checked)
        dialog._results_table.item(1, _COL_SELECT).setCheckState(Qt.CheckState.Checked)
        dialog._mark_selected_rows_checked()

        self.assertEqual(len(dialog._pairs), 1)
        self.assertEqual(dialog._pairs[0].left.item_id, "5")
        self.assertEqual(dialog._results_table.rowCount(), 1)
        self.assertIn("Celkem nalezeno: 1", dialog._results_counts.text())
        self.assertIn("Vybráno: 0", dialog._results_counts.text())
        self.assertIn("Zbývá k posouzení: 1", dialog._results_counts.text())

        self.assertTrue(
            similarity_checked_pair_service.is_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                "area::sekce::1",
                "area::sekce::2",
            )
        )
        self.assertTrue(
            similarity_checked_pair_service.is_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                "area::sekce::3",
                "area::sekce::4",
            )
        )
        self.assertFalse(
            similarity_checked_pair_service.is_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                "area::sekce::5",
                "area::sekce::6",
            )
        )

    def test_marked_pairs_hidden_on_next_analysis(self) -> None:
        catalog = [
            _candidate("10", "Kontrola hasicích přístrojů"),
            _candidate("20", "Kontrola hasicích přístrojů."),
            _candidate("30", "Evidence školení VZV"),
            _candidate("40", "Evidence školení VZV."),
        ]
        dialog = SimilarityAnalysisDialog()
        with patch(
            "moduly.proverky.sluzby.control_point_similarity_analysis.collect_control_point_candidates",
            return_value=catalog,
        ):
            pairs, _ = analyze_control_point_similarities(include_checked=False)
            self.assertGreaterEqual(len(pairs), 2)
            dialog._pairs = list(pairs)
            dialog._show_results()

            # Zaškrtnout první dvě nalezené dvojice (falešné duplicity).
            for row in range(min(2, dialog._results_table.rowCount())):
                dialog._results_table.item(row, _COL_SELECT).setCheckState(
                    Qt.CheckState.Checked
                )
            marked_before = len(dialog._selected_row_indexes())
            self.assertEqual(marked_before, min(2, len(pairs)))
            dialog._mark_selected_rows_checked()

            remaining, _ = analyze_control_point_similarities(include_checked=False)
            self.assertEqual(len(remaining), len(pairs) - marked_before)
            remaining_ids = {item.normalized_ids for item in remaining}
            for pair in pairs[:marked_before]:
                self.assertNotIn(pair.normalized_ids, remaining_ids)


if __name__ == "__main__":
    unittest.main()
