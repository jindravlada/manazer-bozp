"""SIMILARITY-1: UI podobných kontrolních otázek prověrek."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-1-ui-"))
_HOME = _TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_HOME):
    from PySide6.QtWidgets import QApplication, QDialog, QLabel

    from core.services.text_similarity_service import MATCH_TYPE_EXACT, SimilarityMatch
    from moduly.proverky.sluzby.control_point_similarity_service import (
        ControlPointSimilarityCandidate,
        ControlPointSimilarityMatch,
    )
    from moduly.proverky.ui.proverky_knowledge_list_item_dialog import (
        ProverkyKnowledgeListItemDialog,
    )
    from moduly.proverky.ui.similar_control_points_dialog import (
        SimilarControlPointsDialog,
    )


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _match(*, score: float = 1.0, text: str = "Kontrola OOPP") -> ControlPointSimilarityMatch:
    return ControlPointSimilarityMatch(
        match=SimilarityMatch(
            id="area::sekce::bod1",
            text=text,
            match_type=MATCH_TYPE_EXACT if score >= 1.0 else "possible",
            score=score,
        ),
        candidate=ControlPointSimilarityCandidate(
            composite_id="area::sekce::bod1",
            area_id="area",
            area_name="Pracovní prostředí",
            section_id="sekce",
            section_name="OOPP",
            item_id="bod1",
            text=text,
        ),
    )


class Similarity1UiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_find_similar_button_available_for_control_points(self) -> None:
        dialog = ProverkyKnowledgeListItemDialog(
            None,
            title="Upravit položku",
            include_zavaznost=True,
            include_verification_type=True,
            enable_similarity_check=True,
            similarity_area_id="a",
            similarity_section_id="s",
        )
        self.assertTrue(hasattr(dialog, "find_similar_btn"))
        self.assertEqual(dialog.find_similar_btn.text(), "Najít podobné otázky")

    def test_find_similar_button_absent_for_other_lists(self) -> None:
        dialog = ProverkyKnowledgeListItemDialog(
            None,
            title="Upravit položku",
            enable_similarity_check=False,
        )
        self.assertFalse(hasattr(dialog, "find_similar_btn"))

    def test_results_dialog_shows_exact_match_and_location(self) -> None:
        dlg = SimilarControlPointsDialog(None, matches=[_match()])
        self.assertEqual(dlg.windowTitle(), "Podobné kontrolní otázky")
        self.assertEqual(dlg.table.rowCount(), 1)
        self.assertIn("100 %", dlg.table.item(0, 0).text())
        self.assertIn("Přesná shoda", dlg.table.item(0, 0).text())
        self.assertEqual(dlg.table.item(0, 1).text(), "Kontrola OOPP")
        self.assertIn("Prověrky BOZP", dlg.table.item(0, 2).text())
        self.assertIn("Pracovní prostředí", dlg.table.item(0, 2).text())
        self.assertIn("OOPP", dlg.table.item(0, 2).text())

    def test_empty_results_show_info_state(self) -> None:
        dlg = SimilarControlPointsDialog(None, matches=[])
        self.assertFalse(hasattr(dlg, "table"))
        labels = dlg.findChildren(QLabel)
        texts = [label.text() for label in labels]
        self.assertTrue(
            any("Nebyly nalezeny žádné podobné kontrolní otázky." in text for text in texts)
        )

    def test_find_similar_uses_service_and_keeps_save_behavior(self) -> None:
        dialog = ProverkyKnowledgeListItemDialog(
            None,
            title="Upravit položku",
            item={"id": "self", "nazev": "Kontrola OOPP", "popis": ""},
            enable_similarity_check=True,
            similarity_area_id="a",
            similarity_section_id="s",
            similarity_section_items=[
                {"id": "self", "nazev": "Kontrola OOPP"},
                {"id": "other", "nazev": "Kontrola OOPP"},
            ],
        )
        with patch(
            "moduly.proverky.ui.proverky_knowledge_list_item_dialog.find_similar_control_points",
            return_value=[_match()],
        ) as mocked:
            with patch.object(SimilarControlPointsDialog, "exec", return_value=QDialog.DialogCode.Rejected):
                dialog._find_similar_questions()
        mocked.assert_called_once()
        kwargs = mocked.call_args.kwargs
        self.assertIn("a::s::self", kwargs["exclude_composite_ids"])

        # Uložení zůstává standardní – kontrola se nespouští automaticky.
        data = dialog.get_data()
        self.assertEqual(data["nazev"], "Kontrola OOPP")
        self.assertEqual(data["id"], "self")


if __name__ == "__main__":
    unittest.main()
