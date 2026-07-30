"""SIMILARITY-UX-5: ochrana označených dvojic při zavření dialogu."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-ux-5-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication, QDialog

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


def _pair(left_id: str, right_id: str) -> ControlPointSimilarityPair:
    return ControlPointSimilarityPair(
        score=0.9,
        match_type="possible",
        match_label="Možná podobnost",
        left=_candidate(left_id, f"Otázka {left_id}"),
        right=_candidate(right_id, f"Otázka {right_id}"),
    )


class SimilarityUx5CloseGuardTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with get_session() as session:
            session.query(SimilarityCheckedPair).delete()
            session.commit()

    def _dialog_with_pairs(self) -> SimilarityAnalysisDialog:
        dialog = SimilarityAnalysisDialog()
        dialog._pairs = [_pair("1", "2"), _pair("3", "4"), _pair("5", "6")]
        dialog._show_results()
        return dialog

    def test_close_without_selection_skips_prompt(self) -> None:
        dialog = self._dialog_with_pairs()
        with patch.object(
            dialog, "_prompt_pending_bulk_selection_close"
        ) as prompt:
            with patch.object(QDialog, "accept") as accept_mock:
                dialog._request_close()
        prompt.assert_not_called()
        accept_mock.assert_called_once()
        self.assertTrue(dialog._closing)

    def test_close_with_selection_shows_prompt(self) -> None:
        dialog = self._dialog_with_pairs()
        dialog._results_table.item(0, _COL_SELECT).setCheckState(Qt.CheckState.Checked)
        dialog._results_table.item(2, _COL_SELECT).setCheckState(Qt.CheckState.Checked)

        with patch.object(
            dialog,
            "_prompt_pending_bulk_selection_close",
            return_value="cancel",
        ) as prompt:
            dialog._request_close()

        prompt.assert_called_once()
        self.assertFalse(dialog._closing)
        self.assertEqual(dialog._selected_row_indexes(), [0, 2])

    def test_mark_and_close_persists_selection(self) -> None:
        dialog = self._dialog_with_pairs()
        dialog._results_table.item(0, _COL_SELECT).setCheckState(Qt.CheckState.Checked)
        dialog._results_table.item(1, _COL_SELECT).setCheckState(Qt.CheckState.Checked)

        with patch.object(
            dialog,
            "_prompt_pending_bulk_selection_close",
            return_value="mark_and_close",
        ), patch.object(QDialog, "accept") as accept_mock:
            dialog._request_close()

        accept_mock.assert_called_once()
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
        self.assertEqual(len(dialog._pairs), 1)

    def test_discard_close_does_not_persist(self) -> None:
        dialog = self._dialog_with_pairs()
        dialog._results_table.item(0, _COL_SELECT).setCheckState(Qt.CheckState.Checked)

        with patch.object(
            dialog,
            "_prompt_pending_bulk_selection_close",
            return_value="discard",
        ), patch.object(QDialog, "reject") as reject_mock:
            dialog.reject()

        reject_mock.assert_called_once()
        self.assertFalse(
            similarity_checked_pair_service.is_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                "area::sekce::1",
                "area::sekce::2",
            )
        )
        # Výběr se při discard neukládá; seznam výsledků zůstává (dialog se jen zavírá).
        self.assertEqual(len(dialog._pairs), 3)

    def test_cancel_keeps_dialog_open_with_selection(self) -> None:
        dialog = self._dialog_with_pairs()
        dialog._results_table.item(1, _COL_SELECT).setCheckState(Qt.CheckState.Checked)

        with patch.object(
            dialog,
            "_prompt_pending_bulk_selection_close",
            return_value="cancel",
        ), patch.object(QDialog, "reject") as reject_mock:
            dialog.reject()

        reject_mock.assert_not_called()
        self.assertFalse(dialog._closing)
        self.assertEqual(dialog._selected_row_indexes(), [1])

        event = QCloseEvent()
        with patch.object(
            dialog,
            "_prompt_pending_bulk_selection_close",
            return_value="cancel",
        ):
            dialog.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertEqual(dialog._selected_row_indexes(), [1])

    def test_prompt_text_and_default_button(self) -> None:
        dialog = self._dialog_with_pairs()
        dialog._results_table.item(0, _COL_SELECT).setCheckState(Qt.CheckState.Checked)
        dialog._results_table.item(1, _COL_SELECT).setCheckState(Qt.CheckState.Checked)

        from PySide6.QtWidgets import QMessageBox

        captured: dict = {}

        def fake_exec(self):
            captured["text"] = self.text()
            captured["default"] = self.defaultButton().text()
            captured["buttons"] = [btn.text() for btn in self.buttons()]
            # Simulovat Zrušit.
            cancel = next(btn for btn in self.buttons() if btn.text() == "Zrušit")
            self.buttonClicked.emit(cancel)
            return int(QMessageBox.StandardButton.Cancel)

        with patch.object(QMessageBox, "exec", fake_exec):
            result = dialog._prompt_pending_bulk_selection_close()

        self.assertEqual(result, "cancel")
        self.assertIn("Máte označeno 2 dvojic jako správné", captured["text"])
        self.assertIn("Co chcete udělat?", captured["text"])
        self.assertEqual(captured["default"], "Zrušit")
        self.assertIn("Označit a zavřít", captured["buttons"])
        self.assertIn("Zavřít bez uložení", captured["buttons"])
        self.assertIn("Zrušit", captured["buttons"])


if __name__ == "__main__":
    unittest.main()
