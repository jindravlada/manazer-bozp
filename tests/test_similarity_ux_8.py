"""SIMILARITY-UX-8: oddělení správy zkontrolovaných dvojic od analýzy."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-ux-8-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtWidgets import QApplication, QDialog

    from core.database.database_initializer import initialize_database
    from core.database.session import get_session
    from core.shared.modely.similarity_checked_pair import SimilarityCheckedPair
    from core.shared.sluzby.similarity_checked_pair_service import (
        SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
        similarity_checked_pair_service,
    )
    from core.ui.similarity_analysis_dialog import SimilarityAnalysisDialog
    from core.ui.similarity_checked_pairs_dialog import SimilarityCheckedPairsDialog
    from moduly.proverky.sluzby.control_point_similarity_analysis import (
        ControlPointSimilarityPair,
    )
    from moduly.proverky.sluzby.control_point_similarity_service import (
        ControlPointSimilarityCandidate,
    )
    from moduly.sprava_dat.ui.data_quality_tab import DataQualityTab

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


class SimilarityUx8SeparationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with get_session() as session:
            session.query(SimilarityCheckedPair).delete()
            session.commit()

    def test_analysis_has_no_show_checked_option(self) -> None:
        dialog = SimilarityAnalysisDialog()
        self.assertFalse(hasattr(dialog, "_show_checked_setup"))
        self.assertFalse(hasattr(dialog, "_show_checked_results"))
        tab = DataQualityTab()
        self.assertFalse(hasattr(tab, "_show_checked"))

    def test_analysis_shows_only_unresolved_pairs(self) -> None:
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [
            _pair("1", "2"),
            _pair("3", "4", checked=True),
            _pair("5", "6"),
        ]
        dialog._show_results()

        self.assertEqual(len(dialog._pairs), 2)
        self.assertTrue(all(not pair.checked for pair in dialog._pairs))
        self.assertEqual(dialog._results_table.rowCount(), 2)

    def test_manage_button_opens_checked_pairs_dialog(self) -> None:
        dialog = SimilarityAnalysisDialog()
        self.assertEqual(
            dialog._manage_checked_setup_btn.text(),
            "Správa zkontrolovaných dvojic...",
        )
        self.assertEqual(
            dialog._manage_checked_results_btn.text(),
            "Správa zkontrolovaných dvojic...",
        )

        opened: list[SimilarityCheckedPairsDialog] = []

        def tracking_exec(self):
            opened.append(self)
            return QDialog.DialogCode.Accepted

        with patch.object(SimilarityCheckedPairsDialog, "exec", tracking_exec):
            dialog._open_checked_pairs_manager()

        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].windowTitle(), "Správa zkontrolovaných dvojic")

    def test_management_dialog_lists_checked_pairs(self) -> None:
        similarity_checked_pair_service.mark_checked(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            "area::sekce::1",
            "area::sekce::2",
        )
        mgr = SimilarityCheckedPairsDialog()
        self.assertEqual(mgr.windowTitle(), "Správa zkontrolovaných dvojic")
        self.assertEqual(mgr.table.rowCount(), 1)
        self.assertFalse(mgr._empty_label.isVisibleTo(mgr))
        texts = {
            mgr.table.item(0, col).text()
            for col in range(4)
            if mgr.table.item(0, col) is not None
        }
        # Bez kandidátů v DB zůstávají ID; důležité je, že řádek existuje.
        self.assertTrue(any("area::sekce::" in text for text in texts) or len(texts) >= 1)

    def test_closing_management_does_not_clear_analysis(self) -> None:
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [_pair("1", "2"), _pair("3", "4")]
        dialog._show_results()
        before = list(dialog._pairs)

        with patch.object(
            SimilarityCheckedPairsDialog,
            "exec",
            return_value=QDialog.DialogCode.Accepted,
        ):
            dialog._open_checked_pairs_manager()

        self.assertEqual(dialog._pairs, before)
        self.assertEqual(dialog._results_table.rowCount(), 2)

    def test_worker_never_includes_checked(self) -> None:
        dialog = SimilarityAnalysisDialog()
        with patch(
            "core.ui.similarity_analysis_dialog.analyze_control_point_similarities",
            return_value=([], False),
        ) as analyze_mock:
            dialog._start_analysis()
            if dialog._worker is not None:
                dialog._worker.wait(3000)
        self.assertFalse(analyze_mock.call_args.kwargs.get("include_checked", True))


if __name__ == "__main__":
    unittest.main()
