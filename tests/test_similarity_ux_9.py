"""SIMILARITY-UX-9: vrácení zkontrolovaných dvojic zpět do analýzy."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-ux-9-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtGui import QKeySequence
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from core.database.database_initializer import initialize_database
    from core.database.session import get_session
    from core.shared.modely.similarity_checked_pair import SimilarityCheckedPair
    from core.shared.sluzby.similarity_checked_pair_service import (
        SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
        similarity_checked_pair_service,
    )
    from core.ui.similarity_checked_pairs_dialog import SimilarityCheckedPairsDialog
    from moduly.proverky.sluzby.control_point_similarity_analysis import (
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


def _mark(left: str, right: str) -> None:
    similarity_checked_pair_service.mark_checked(
        SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
        f"area::sekce::{left}",
        f"area::sekce::{right}",
    )


class SimilarityUx9ReturnTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with get_session() as session:
            session.query(SimilarityCheckedPair).delete()
            session.commit()

    def test_return_button_disabled_without_selection(self) -> None:
        _mark("1", "2")
        dialog = SimilarityCheckedPairsDialog()
        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertFalse(dialog.return_to_analysis_btn.isEnabled())
        self.assertIn("1", dialog._count_label.text())

    def test_select_single_row_enables_button(self) -> None:
        _mark("1", "2")
        _mark("3", "4")
        dialog = SimilarityCheckedPairsDialog()
        dialog.table.selectRow(0)
        self.assertTrue(dialog.return_to_analysis_btn.isEnabled())
        self.assertEqual(len(dialog._selected_pair_ids()), 1)

    def test_select_multiple_rows(self) -> None:
        _mark("1", "2")
        _mark("3", "4")
        _mark("5", "6")
        dialog = SimilarityCheckedPairsDialog()
        dialog.table.setSelectionMode(
            dialog.table.SelectionMode.ExtendedSelection
        )
        dialog.table.selectRow(0)
        dialog.table.selectionModel().select(
            dialog.table.model().index(2, 0),
            dialog.table.selectionModel().SelectionFlag.Select
            | dialog.table.selectionModel().SelectionFlag.Rows,
        )
        self.assertEqual(len(dialog._selected_pair_ids()), 2)
        self.assertTrue(dialog.return_to_analysis_btn.isEnabled())

    def test_ctrl_a_selects_all(self) -> None:
        _mark("1", "2")
        _mark("3", "4")
        dialog = SimilarityCheckedPairsDialog()
        dialog.table.setFocus()
        dialog.table.selectAll()
        self.assertEqual(len(dialog._selected_pair_ids()), 2)

        # Ověření, že Ctrl+A je dostupný standardní zkratkou tabulky.
        dialog.table.clearSelection()
        self.assertEqual(len(dialog._selected_pair_ids()), 0)
        QTest.keySequence(dialog.table, QKeySequence.StandardKey.SelectAll)
        self.assertEqual(len(dialog._selected_pair_ids()), 2)

    def test_return_removes_from_evidence_and_table(self) -> None:
        _mark("1", "2")
        _mark("3", "4")
        dialog = SimilarityCheckedPairsDialog()
        all_before = {
            (r.left_entity_id, r.right_entity_id)
            for r in similarity_checked_pair_service.repository.list_for_type(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT
            )
        }
        self.assertEqual(len(all_before), 2)

        dialog.table.selectRow(0)
        selected = dialog._selected_pair_ids()[0]
        dialog._return_selected_to_analysis()

        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertIn("1", dialog._count_label.text())
        self.assertFalse(
            similarity_checked_pair_service.is_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                selected[0],
                selected[1],
            )
        )
        remaining = all_before - {selected}
        self.assertEqual(len(remaining), 1)
        left, right = next(iter(remaining))
        self.assertTrue(
            similarity_checked_pair_service.is_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                left,
                right,
            )
        )

    def test_returned_pair_appears_in_next_analysis(self) -> None:
        catalog = [
            _candidate("a1", "Dodržujte bezpečnostní předpisy"),
            _candidate("a2", "Dodržujte bezpečnostní předpisy."),
        ]
        with patch(
            "moduly.proverky.sluzby.control_point_similarity_analysis.collect_control_point_candidates",
            return_value=catalog,
        ), patch(
            "core.ui.similarity_checked_pairs_dialog.collect_control_point_candidates",
            return_value=catalog,
        ):
            similarity_checked_pair_service.mark_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                catalog[0].composite_id,
                catalog[1].composite_id,
            )
            self.assertEqual(
                analyze_control_point_similarities(include_checked=False)[0],
                [],
            )

            dialog = SimilarityCheckedPairsDialog()
            self.assertEqual(dialog.table.rowCount(), 1)
            dialog.table.selectRow(0)
            dialog._return_selected_to_analysis()

            self.assertEqual(dialog.table.rowCount(), 0)
            self.assertIn("0", dialog._count_label.text())
            pairs, _ = analyze_control_point_similarities(include_checked=False)
            self.assertEqual(len(pairs), 1)
            self.assertFalse(pairs[0].checked)

    def test_return_all_via_select_all_updates_count(self) -> None:
        _mark("1", "2")
        _mark("3", "4")
        dialog = SimilarityCheckedPairsDialog()
        dialog.table.selectAll()
        dialog._return_selected_to_analysis()
        self.assertEqual(dialog.table.rowCount(), 0)
        self.assertIn("0", dialog._count_label.text())
        self.assertFalse(dialog.return_to_analysis_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
