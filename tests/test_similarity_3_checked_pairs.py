"""SIMILARITY-3: evidence zkontrolovaných dvojic podobných záznamů."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

_TMP = Path(tempfile.mkdtemp(prefix="similarity-3-"))
_HOME = _TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_HOME):
    from PySide6.QtWidgets import QApplication, QMessageBox

    from core.database.database_initializer import initialize_database
    from core.database.session import get_session
    from core.shared.modely.similarity_checked_pair import SimilarityCheckedPair
    from core.shared.sluzby.similarity_checked_pair_service import (
        SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
        normalize_similarity_pair_ids,
        similarity_checked_pair_service,
    )
    from core.ui.similarity_analysis_dialog import SimilarityAnalysisDialog
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


class Similarity3ServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.query(SimilarityCheckedPair).delete()
            session.commit()

    def test_normalize_pair_order(self) -> None:
        self.assertEqual(
            normalize_similarity_pair_ids("28", "15"),
            ("15", "28"),
        )
        self.assertEqual(
            normalize_similarity_pair_ids("15", "28"),
            ("15", "28"),
        )
        self.assertEqual(
            normalize_similarity_pair_ids("b::2", "a::1"),
            ("a::1", "b::2"),
        )

    def test_create_checked_record(self) -> None:
        record = similarity_checked_pair_service.mark_checked(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            "area::s::28",
            "area::s::15",
            checked_by="tester",
        )
        self.assertEqual(record.left_entity_id, "area::s::15")
        self.assertEqual(record.right_entity_id, "area::s::28")
        self.assertEqual(record.checked_by, "tester")
        self.assertTrue(
            similarity_checked_pair_service.is_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                "area::s::15",
                "area::s::28",
            )
        )

    def test_unique_pair_constraint(self) -> None:
        similarity_checked_pair_service.mark_checked(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            "x",
            "y",
        )
        # Služba je idempotentní.
        again = similarity_checked_pair_service.mark_checked(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            "y",
            "x",
        )
        self.assertEqual(again.left_entity_id, "x")
        keys = similarity_checked_pair_service.list_checked_keys(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT
        )
        self.assertEqual(keys, {("x", "y")})

        # Přímý zápis stejné dvojice musí narazit na unikátní omezení.
        with get_session() as session:
            session.add(
                SimilarityCheckedPair(
                    entity_type=SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                    left_entity_id="x",
                    right_entity_id="y",
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

    def test_hide_checked_pair_from_analysis(self) -> None:
        catalog = [
            _candidate("a1", "Kontrola hasicích přístrojů"),
            _candidate("a2", "Kontrola hasicích přístrojů."),
        ]
        with patch(
            "moduly.proverky.sluzby.control_point_similarity_analysis.collect_control_point_candidates",
            return_value=catalog,
        ):
            pairs, _ = analyze_control_point_similarities(include_checked=False)
            self.assertEqual(len(pairs), 1)

            similarity_checked_pair_service.mark_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                catalog[0].composite_id,
                catalog[1].composite_id,
            )
            hidden, _ = analyze_control_point_similarities(include_checked=False)
            self.assertEqual(hidden, [])

            shown, _ = analyze_control_point_similarities(include_checked=True)
            self.assertEqual(len(shown), 1)
            self.assertTrue(shown[0].checked)

    def test_unmark_makes_pair_visible_again(self) -> None:
        catalog = [
            _candidate("b1", "Dodržujte bezpečnostní předpisy"),
            _candidate("b2", "Dodržujte bezpečnostní předpisy."),
        ]
        with patch(
            "moduly.proverky.sluzby.control_point_similarity_analysis.collect_control_point_candidates",
            return_value=catalog,
        ):
            similarity_checked_pair_service.mark_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                catalog[1].composite_id,
                catalog[0].composite_id,
            )
            self.assertEqual(
                analyze_control_point_similarities(include_checked=False)[0],
                [],
            )
            similarity_checked_pair_service.unmark_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                catalog[0].composite_id,
                catalog[1].composite_id,
            )
            pairs, _ = analyze_control_point_similarities(include_checked=False)
            self.assertEqual(len(pairs), 1)
            self.assertFalse(pairs[0].checked)


class Similarity3UiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with get_session() as session:
            session.query(SimilarityCheckedPair).delete()
            session.commit()

    def test_mark_checked_removes_from_results(self) -> None:
        dialog = SimilarityAnalysisDialog()
        pair = ControlPointSimilarityPair(
            score=1.0,
            match_type="exact",
            match_label="Přesná shoda",
            left=_candidate("1", "Kontrola OOPP"),
            right=_candidate("2", "Kontrola OOPP."),
            checked=False,
        )
        dialog._pairs = [pair]
        dialog._show_results()
        dialog._results_table.selectRow(0)

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog._mark_selected_checked()

        self.assertEqual(dialog._pairs, [])
        self.assertTrue(
            similarity_checked_pair_service.is_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                pair.left.composite_id,
                pair.right.composite_id,
            )
        )

    def test_show_checked_checkbox_default_off(self) -> None:
        dialog = SimilarityAnalysisDialog()
        self.assertFalse(dialog._show_checked_setup.isChecked())
        self.assertFalse(dialog._show_checked_results.isChecked())

    def test_unmark_action_updates_row(self) -> None:
        dialog = SimilarityAnalysisDialog()
        pair = ControlPointSimilarityPair(
            score=1.0,
            match_type="exact",
            match_label="Přesná shoda",
            left=_candidate("3", "Text A"),
            right=_candidate("4", "Text A."),
            checked=True,
        )
        similarity_checked_pair_service.mark_checked(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            pair.left.composite_id,
            pair.right.composite_id,
        )
        dialog._pairs = [pair]
        dialog._show_checked_results.blockSignals(True)
        dialog._show_checked_results.setChecked(True)
        dialog._show_checked_results.blockSignals(False)
        dialog._show_results()
        dialog._results_table.selectRow(0)
        self.assertIn("Zkontrolováno", dialog._results_table.item(0, 2).text())

        dialog._unmark_selected_checked()
        self.assertFalse(
            similarity_checked_pair_service.is_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                pair.left.composite_id,
                pair.right.composite_id,
            )
        )
        self.assertEqual(len(dialog._pairs), 1)
        self.assertFalse(dialog._pairs[0].checked)


if __name__ == "__main__":
    unittest.main()
