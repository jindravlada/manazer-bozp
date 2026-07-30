"""SIMILARITY-PERF-1: diagnostika výkonu načítání výsledků."""

from __future__ import annotations

import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-perf-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtWidgets import QApplication

    from core.database.database_initializer import initialize_database
    from core.ui.similarity_analysis_dialog import SimilarityAnalysisDialog
    from moduly.proverky.sluzby.control_point_similarity_analysis import (
        ControlPointSimilarityPair,
        analyze_control_point_similarities,
    )
    from moduly.proverky.sluzby.control_point_similarity_service import (
        ControlPointSimilarityCandidate,
    )
    from moduly.proverky.sluzby.similarity_performance import (
        SimilarityPerformanceTimings,
        new_timings_if_enabled,
        similarity_perf_enabled,
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


class SimilarityPerf1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_report_format(self) -> None:
        timings = SimilarityPerformanceTimings(
            db_s=0.182,
            checked_s=0.041,
            prepare_s=0.337,
            table_s=2.914,
        )
        report = timings.format_report()
        self.assertIn("SIMILARITY PERFORMANCE", report)
        self.assertIn("Načtení DB", report)
        self.assertIn("0.182 s", report)
        self.assertIn("Načtení checked", report)
        self.assertIn("0.041 s", report)
        self.assertIn("Příprava dat", report)
        self.assertIn("0.337 s", report)
        self.assertIn("Vytvoření tabulky", report)
        self.assertIn("2.914 s", report)
        self.assertIn("Celkem", report)
        self.assertIn("3.474 s", report)

    def test_disabled_when_logger_not_debug(self) -> None:
        logger = logging.getLogger("moduly.proverky.sluzby.similarity_performance")
        previous = logger.level
        logger.setLevel(logging.WARNING)
        try:
            self.assertFalse(similarity_perf_enabled())
            self.assertIsNone(new_timings_if_enabled())
        finally:
            logger.setLevel(previous)

    def test_analyze_fills_timings_in_debug(self) -> None:
        logger = logging.getLogger("moduly.proverky.sluzby.similarity_performance")
        previous = logger.level
        logger.setLevel(logging.DEBUG)
        try:
            catalog = [
                _candidate("1", "Kontrola hasicích přístrojů"),
                _candidate("2", "Kontrola hasicích přístrojů."),
            ]
            perf = SimilarityPerformanceTimings()
            with patch(
                "moduly.proverky.sluzby.control_point_similarity_analysis.collect_control_point_candidates",
                return_value=catalog,
            ):
                pairs, cancelled = analyze_control_point_similarities(
                    include_checked=False,
                    performance=perf,
                )
            self.assertFalse(cancelled)
            self.assertEqual(len(pairs), 1)
            self.assertGreaterEqual(perf.db_s, 0.0)
            self.assertGreaterEqual(perf.checked_s, 0.0)
            self.assertGreaterEqual(perf.prepare_s, 0.0)
            self.assertEqual(perf.table_s, 0.0)
        finally:
            logger.setLevel(previous)

    def test_show_results_adds_table_timing_and_logs(self) -> None:
        logger = logging.getLogger("moduly.proverky.sluzby.similarity_performance")
        previous = logger.level
        logger.setLevel(logging.DEBUG)
        try:
            dialog = SimilarityAnalysisDialog()
            dialog._pairs = [
                ControlPointSimilarityPair(
                    score=1.0,
                    match_type="exact",
                    match_label="Přesná shoda",
                    left=_candidate("1", "A"),
                    right=_candidate("2", "A."),
                    checked=True,
                )
            ]
            perf = SimilarityPerformanceTimings(db_s=0.01, checked_s=0.02, prepare_s=0.03)
            dialog._pending_performance = perf

            with self.assertLogs(logger, level=logging.DEBUG) as captured:
                dialog._show_results()

            self.assertGreater(perf.table_s, 0.0)
            joined = "\n".join(captured.output)
            self.assertIn("SIMILARITY PERFORMANCE", joined)
            self.assertIn("Vytvoření tabulky", joined)
            self.assertIn("Celkem", joined)
            self.assertEqual(dialog._results_table.rowCount(), 1)
            self.assertIn("Zkontrolováno", dialog._results_table.item(0, 1).text())
        finally:
            logger.setLevel(previous)

    def test_behavior_unchanged_without_debug(self) -> None:
        logger = logging.getLogger("moduly.proverky.sluzby.similarity_performance")
        previous = logger.level
        logger.setLevel(logging.WARNING)
        try:
            dialog = SimilarityAnalysisDialog()
            dialog._pairs = [
                ControlPointSimilarityPair(
                    score=0.9,
                    match_type="possible",
                    match_label="Možná podobnost",
                    left=_candidate("3", "X"),
                    right=_candidate("4", "Y"),
                )
            ]
            dialog._show_results()
            self.assertEqual(dialog._results_table.rowCount(), 1)
            self.assertIn("Celkem nalezeno: 1", dialog._results_counts.text())
        finally:
            logger.setLevel(previous)


if __name__ == "__main__":
    unittest.main()
