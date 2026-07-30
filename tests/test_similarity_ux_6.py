"""SIMILARITY-UX-6: oddělení výběru a stavu zkontrolování."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-ux-6-"))
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
        _COL_SIMILARITY,
        _COL_STATUS,
    )
    from moduly.proverky.sluzby.control_point_similarity_analysis import (
        ControlPointSimilarityPair,
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


def _pair(
    left_id: str,
    right_id: str,
    *,
    checked: bool = False,
) -> ControlPointSimilarityPair:
    return ControlPointSimilarityPair(
        score=0.95,
        match_type="possible",
        match_label="Možná podobnost",
        left=_candidate(left_id, f"Otázka {left_id}"),
        right=_candidate(right_id, f"Otázka {right_id}"),
        checked=checked,
    )


class SimilarityUx6SeparationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with get_session() as session:
            session.query(SimilarityCheckedPair).delete()
            session.commit()

    def test_column_order_status_after_similarity(self) -> None:
        dialog = SimilarityAnalysisDialog()
        headers = [
            dialog._results_table.horizontalHeaderItem(i).text()
            for i in range(dialog._results_table.columnCount())
        ]
        self.assertEqual(headers[_COL_SELECT], "")
        self.assertEqual(headers[_COL_SIMILARITY], "Podobnost")
        self.assertEqual(headers[_COL_STATUS], "Stav")
        self.assertLess(_COL_SIMILARITY, _COL_STATUS)

    def test_checkbox_is_only_for_current_selection(self) -> None:
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [_pair("1", "2"), _pair("3", "4")]
        dialog._show_results()

        select = dialog._results_table.item(0, _COL_SELECT)
        self.assertEqual(select.checkState(), Qt.CheckState.Unchecked)
        self.assertTrue(select.flags() & Qt.ItemFlag.ItemIsUserCheckable)
        select.setCheckState(Qt.CheckState.Checked)
        self.assertEqual(select.checkState(), Qt.CheckState.Checked)
        self.assertEqual(dialog._results_table.item(0, _COL_STATUS).text(), "")
        self.assertNotIn("Zkontrolováno", select.text())

    def test_analysis_filters_out_checked_pairs(self) -> None:
        """UX-8: zkontrolované dvojice se v analýze nezobrazují (Stav zůstává prázdný)."""
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [_pair("10", "20", checked=True), _pair("11", "21")]
        dialog._show_results()

        self.assertEqual(dialog._results_table.rowCount(), 1)
        self.assertEqual(
            dialog._results_table.item(0, _COL_SELECT).checkState(),
            Qt.CheckState.Unchecked,
        )
        self.assertEqual(dialog._results_table.item(0, _COL_STATUS).text(), "")

    def test_bulk_mark_still_works(self) -> None:
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [_pair("1", "2"), _pair("3", "4")]
        dialog._show_results()
        dialog._results_table.item(0, _COL_SELECT).setCheckState(Qt.CheckState.Checked)
        dialog._mark_selected_rows_checked()

        self.assertEqual(len(dialog._pairs), 1)
        self.assertTrue(
            similarity_checked_pair_service.is_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                "area::sekce::1",
                "area::sekce::2",
            )
        )

    def test_status_empty_after_mark_and_refresh(self) -> None:
        dialog = SimilarityAnalysisDialog()
        pair = _pair("5", "6")
        dialog._pairs = [pair]
        dialog._show_results()
        self.assertEqual(dialog._results_table.item(0, _COL_STATUS).text(), "")

        similarity_checked_pair_service.mark_checked(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            pair.left.composite_id,
            pair.right.composite_id,
        )
        dialog._pairs = [_pair("5", "6", checked=True)]
        dialog._show_results()

        self.assertEqual(dialog._results_table.rowCount(), 0)
        self.assertEqual(dialog._pairs, [])


if __name__ == "__main__":
    unittest.main()
