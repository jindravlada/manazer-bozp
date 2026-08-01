"""SIMILARITY-UX-1: Analýza podobností ve Správě dat → Kvalita dat."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-ux-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import importlib

    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QMenuBar, QTabWidget

    from core.ui.similarity_analysis_dialog import (
        SimilarityAnalysisDialog,
    )
    from core.windows.main_window import MainWindow
    from moduly.sprava_dat.ui.data_quality_tab import DataQualityTab
    from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage
    from moduly.sprava_dat.ui.tab_constants import (
        TAB_BACKUP,
        TAB_CODEBOOKS,
        TAB_DATA_QUALITY,
        TAB_DIAGNOSTICS,
        TAB_ORDER,
        TAB_SUMMARY,
        TAB_TRANSFER,
    )


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class SimilarityUx1PageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_sprava_dat_has_data_quality_tab(self) -> None:
        page = SpravaDatPage()
        tabs = page.findChild(QTabWidget)
        assert tabs is not None
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        self.assertEqual(labels, list(TAB_ORDER))
        self.assertIn(TAB_DATA_QUALITY, labels)
        self.assertIsInstance(page.data_quality_tab, DataQualityTab)

    def test_other_tabs_unchanged(self) -> None:
        self.assertEqual(
            list(TAB_ORDER),
            [
                TAB_SUMMARY,
                TAB_BACKUP,
                TAB_TRANSFER,
                TAB_CODEBOOKS,
                TAB_DIAGNOSTICS,
                TAB_DATA_QUALITY,
            ],
        )

    def test_data_quality_tab_has_similarity_section(self) -> None:
        tab = DataQualityTab()
        self.assertTrue(hasattr(tab, "start_analysis_btn"))
        self.assertEqual(tab.start_analysis_btn.text(), "Spustit analýzu")
        self.assertFalse(hasattr(tab, "_show_checked"))
        self.assertFalse(hasattr(tab, "_scope_checks"))


class SimilarityUx1LaunchTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_start_opens_existing_similarity_dialog(self) -> None:
        tab = DataQualityTab()

        created: list[SimilarityAnalysisDialog] = []
        original_init = SimilarityAnalysisDialog.__init__

        def tracking_init(self, parent=None, *, auto_start=False):
            original_init(self, parent, auto_start=False)
            created.append(self)
            self._auto_start_arg = auto_start

        with patch.object(SimilarityAnalysisDialog, "__init__", tracking_init), patch.object(
            SimilarityAnalysisDialog, "exec", return_value=0
        ) as exec_mock:
            tab._start_similarity_analysis()

        self.assertEqual(len(created), 1)
        self.assertFalse(created[0]._auto_start_arg)
        exec_mock.assert_called_once()

    def test_start_uses_analyze_domain_similarities(self) -> None:
        dialog = SimilarityAnalysisDialog(auto_start=False)
        with patch.object(dialog, "_refresh_scope_estimates"), patch(
            "core.ui.similarity_analysis_dialog.analyze_domain_similarities",
            return_value=([], False),
        ) as analyze_mock, patch(
            "core.ui.similarity_analysis_dialog.requires_large_analysis_confirmation",
            return_value=False,
        ):
            dialog._start_analysis()
            if dialog._worker is not None:
                dialog._worker.wait(3000)
        analyze_mock.assert_called()
        kwargs = analyze_mock.call_args.kwargs
        self.assertFalse(kwargs.get("include_checked", True))


class SimilarityUx1MenuTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_tools_menu_removed_from_main_window(self) -> None:
        with patch.object(MainWindow, "_load_modules"):
            window = MainWindow()
        self.assertFalse(hasattr(window, "tools_menu"))
        menu_bar = window.menuBar()
        self.assertIsInstance(menu_bar, QMenuBar)
        titles = [action.text() for action in menu_bar.actions()]
        self.assertNotIn("Nástroje", titles)
        self.assertFalse(
            any("Analýza podobností" in title for title in titles)
        )


if __name__ == "__main__":
    unittest.main()
