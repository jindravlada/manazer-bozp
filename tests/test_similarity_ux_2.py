"""SIMILARITY-UX-2: maximalizace dialogu a tooltipy elidovaných buněk."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-ux-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDialog, QTableWidget, QTableWidgetItem

    from core.ui.similarity_analysis_dialog import (
        SimilarityAnalysisDialog,
        _RESULT_LOCATION_COLUMNS,
        _RESULT_QUESTION_COLUMNS,
        _RESULT_TEXT_COLUMNS,
    )
    from core.widgets.dialog_utils import prepare_work_dialog_maximized
    from core.widgets.info_tooltip import wrap_tooltip_text
    from core.widgets.table_utils import (
        refresh_elided_cell_tooltips,
        table_cell_text_is_elided,
    )
    from moduly.proverky.sluzby.control_point_similarity_analysis import (
        ControlPointSimilarityPair,
    )
    from moduly.proverky.sluzby.control_point_similarity_service import (
        ControlPointSimilarityCandidate,
    )


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _candidate(
    cid: str,
    text: str,
    *,
    area_name: str = "Oblast",
    section_name: str = "Sekce",
) -> ControlPointSimilarityCandidate:
    return ControlPointSimilarityCandidate(
        composite_id=f"a::s::{cid}",
        area_id="a",
        area_name=area_name,
        section_id="s",
        section_name=section_name,
        item_id=cid,
        text=text,
    )


class SimilarityUx2MaximizeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_exec_opens_maximized(self) -> None:
        dialog = SimilarityAnalysisDialog()
        with (
            patch(
                "core.ui.similarity_analysis_dialog.prepare_work_dialog_maximized",
                wraps=prepare_work_dialog_maximized,
            ) as mock_prepare,
            patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected),
        ):
            dialog.exec()
        mock_prepare.assert_called_once_with(dialog)
        self.assertTrue(dialog.windowState() & Qt.WindowState.WindowMaximized)
        self.assertFalse(dialog.windowState() & Qt.WindowState.WindowFullScreen)

    def test_normal_restore_keeps_resizable_window(self) -> None:
        dialog = SimilarityAnalysisDialog()
        prepare_work_dialog_maximized(dialog)
        QApplication.processEvents()
        self.assertTrue(dialog.windowState() & Qt.WindowState.WindowMaximized)

        dialog.showNormal()
        dialog.resize(900, 620)
        QApplication.processEvents()

        self.assertFalse(dialog.windowState() & Qt.WindowState.WindowMaximized)
        self.assertFalse(dialog.isFullScreen())
        self.assertEqual(dialog.width(), 900)
        self.assertEqual(dialog.height(), 620)
        dialog.resize(750, 500)
        QApplication.processEvents()
        self.assertEqual(dialog.width(), 750)
        self.assertEqual(dialog.height(), 500)


class SimilarityUx2TooltipTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_short_text_has_no_tooltip(self) -> None:
        table = QTableWidget(1, 1)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setColumnWidth(0, 400)
        table.setItem(0, 0, QTableWidgetItem("Krátký text"))
        refresh_elided_cell_tooltips(table, (0,))
        self.assertFalse(table_cell_text_is_elided(table, 0, 0))
        self.assertEqual(table.item(0, 0).toolTip(), "")

    def test_long_text_gets_full_tooltip(self) -> None:
        long_text = "Kontrola OOPP a dalších povinností " * 8
        table = QTableWidget(1, 1)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setColumnWidth(0, 80)
        table.setItem(0, 0, QTableWidgetItem(long_text))
        refresh_elided_cell_tooltips(table, (0,))
        self.assertTrue(table_cell_text_is_elided(table, 0, 0))
        self.assertEqual(table.item(0, 0).toolTip(), wrap_tooltip_text(long_text))

    def test_results_table_tooltips_for_four_text_columns(self) -> None:
        dialog = SimilarityAnalysisDialog()
        long_q1 = "První velmi dlouhá kontrolní otázka o bezpečnosti práce " * 6
        long_area1 = "Velmi dlouhý název oblasti pro umístění první " * 4
        long_sec1 = "Velmi dlouhý název sekce pro umístění první " * 4
        long_q2 = "Druhá velmi dlouhá kontrolní otázka o ochraně zdraví " * 6
        long_area2 = "Jiná oblast s dlouhým názvem pro umístění druhé " * 4
        long_sec2 = "Jiná sekce s dlouhým názvem pro umístění druhé " * 4
        short = "OK"

        dialog._pairs = [
            ControlPointSimilarityPair(
                score=0.9,
                match_type="possible",
                match_label="Možná podobnost",
                left=_candidate("1", long_q1, area_name=long_area1, section_name=long_sec1),
                right=_candidate("2", long_q2, area_name=long_area2, section_name=long_sec2),
            ),
            ControlPointSimilarityPair(
                score=0.8,
                match_type="possible",
                match_label="Možná podobnost",
                left=_candidate("3", short, area_name="A", section_name="B"),
                right=_candidate("4", short, area_name="A", section_name="B"),
            ),
        ]
        dialog._show_results()
        dialog.resize(1000, 700)
        dialog.show()
        QApplication.processEvents()

        table = dialog._results_table
        header = table.horizontalHeader()
        for column in _RESULT_TEXT_COLUMNS:
            header.setSectionResizeMode(column, header.ResizeMode.Interactive)
            table.setColumnWidth(column, 70)
        QApplication.processEvents()
        dialog._refresh_result_tooltips()

        self.assertEqual(table.textElideMode(), Qt.TextElideMode.ElideRight)

        for column in _RESULT_QUESTION_COLUMNS:
            self.assertTrue(
                table_cell_text_is_elided(table, 0, column),
                f"sloupec {column} má být zkrácen",
            )
            tip = table.item(0, column).toolTip()
            self.assertTrue(tip, f"sloupec {column} má mít tooltip")
            full = table.item(0, column).text()
            self.assertEqual(tip, wrap_tooltip_text(full))

        pair0 = dialog._pair_at_row(0)
        self.assertIsNotNone(pair0)
        self.assertEqual(
            table.item(0, 4).toolTip(),
            wrap_tooltip_text(pair0.left.location_label),
        )
        self.assertEqual(
            table.item(0, 6).toolTip(),
            wrap_tooltip_text(pair0.right.location_label),
        )
        self.assertNotEqual(table.item(0, 4).text(), pair0.left.location_label)
        self.assertIn(table.item(0, 4).text(), pair0.left.location_label)

        for column in _RESULT_TEXT_COLUMNS:
            table.setColumnWidth(column, 500)
        QApplication.processEvents()
        dialog._refresh_result_tooltips()
        for column in _RESULT_QUESTION_COLUMNS:
            self.assertFalse(
                table_cell_text_is_elided(table, 1, column),
                f"krátký text ve sloupci {column} nemá být zkrácen",
            )
            self.assertEqual(table.item(1, column).toolTip(), "")

        pair1 = dialog._pair_at_row(1)
        self.assertIsNotNone(pair1)
        self.assertEqual(
            table.item(1, 4).toolTip(),
            wrap_tooltip_text(pair1.left.location_label),
        )
        self.assertEqual(
            table.item(1, 6).toolTip(),
            wrap_tooltip_text(pair1.right.location_label),
        )
        for column in _RESULT_LOCATION_COLUMNS:
            self.assertTrue(table.item(1, column).toolTip())


if __name__ == "__main__":
    unittest.main()
