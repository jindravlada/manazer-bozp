"""MU-UX-HYPOTHESIS-TABS-1 – podzáložky Hypotézy / Zjištění."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QTabWidget

from moduly.vysetrovani_mu.ui.mu_findings_widget import (
    INNER_TAB_FINDINGS,
    INNER_TAB_HYPOTHESES,
    MuFindingsWidget,
)


class MuUxHypothesisTabs1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.widget = MuFindingsWidget()

    def tearDown(self) -> None:
        self.widget.close()
        self.widget.deleteLater()

    def _tab_titles(self) -> list[str]:
        tabs = self.widget.inner_tabs
        return [tabs.tabText(i) for i in range(tabs.count())]

    def test_two_subtabs_in_order(self) -> None:
        self.assertIsInstance(self.widget.inner_tabs, QTabWidget)
        self.assertEqual(self._tab_titles(), [INNER_TAB_HYPOTHESES, INNER_TAB_FINDINGS])
        self.assertNotIn("Bariéry", self._tab_titles())

    def test_hypotheses_contains_ishikawa(self) -> None:
        self.assertIs(self.widget.ishikawa_widget.parentWidget(), self.widget.inner_tabs.widget(0))
        labels = {btn.text() for btn in self.widget.ishikawa_widget.findChildren(QPushButton)}
        self.assertIn("Přidat příčinu", labels)
        self.assertIn("Upravit", labels)
        self.assertIn("Odebrat", labels)
        self.assertIn("Vytvořit zjištění", labels)
        self.assertIn("Řetězec příčin", labels)

    def test_findings_tab_preserves_controls(self) -> None:
        labels = {btn.text() for btn in self.widget.findChildren(QPushButton)}
        self.assertIn("Přidat", labels)
        self.assertIn("Upravit", labels)
        self.assertIn("Smazat", labels)
        self.assertTrue(self.widget.summary_panel.isWidgetType())
        self.assertTrue(self.widget.table.isWidgetType())
        self.assertTrue(self.widget.empty_label.isWidgetType())

    def test_focus_field_switches_subtab(self) -> None:
        self.widget.inner_tabs.setCurrentIndex(1)
        focused = self.widget.focus_field("ishikawa")
        self.assertEqual(self.widget.inner_tabs.tabText(self.widget.inner_tabs.currentIndex()), INNER_TAB_HYPOTHESES)
        self.assertIs(focused, self.widget.ishikawa_widget.table)

        focused = self.widget.focus_field("zjištění")
        self.assertEqual(self.widget.inner_tabs.tabText(self.widget.inner_tabs.currentIndex()), INNER_TAB_FINDINGS)
        self.assertIs(focused, self.widget.table)

    def test_ishikawa_json_roundtrip_unchanged(self) -> None:
        payload = {
            "causes": [
                {
                    "id": "c1",
                    "category": "Člověk",
                    "description": "Neopatrnost",
                    "status": "hypotéza",
                    "level": "bezprostřední",
                    "factors": [],
                }
            ]
        }
        raw = json.dumps(payload, ensure_ascii=False)
        self.widget.load_ishikawa_json(raw)
        loaded = json.loads(self.widget.get_ishikawa_json())
        causes = loaded.get("causes", loaded if isinstance(loaded, list) else [])
        self.assertEqual(causes[0]["description"], "Neopatrnost")
        self.assertEqual(causes[0]["id"], "c1")

    def test_create_finding_from_hypothesis_still_wired(self) -> None:
        self.assertTrue(callable(self.widget.ishikawa_widget.create_finding))
        # Callback na refresh zjištění zůstává napojený.
        self.assertIsNotNone(self.widget.ishikawa_widget._on_findings_changed)
        self.assertEqual(
            self.widget.ishikawa_widget._on_findings_changed.__func__,
            self.widget.refresh.__func__,
        )

    def test_ready_for_barriers_slot(self) -> None:
        """Mezi Hypotézy a Zjištění lze později vložit Bariéry bez změny pořadí konců."""
        titles = self._tab_titles()
        self.assertEqual(titles[0], INNER_TAB_HYPOTHESES)
        self.assertEqual(titles[-1], INNER_TAB_FINDINGS)

    def test_dialog_navigation_switches_inner_tab(self) -> None:
        from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog

        dialog = MagicMock()
        dialog.tabs = QTabWidget()
        dialog.tabs.addTab(self.widget, "Zjištění")
        dialog.findings_widget = self.widget
        dialog._tab_index = lambda name: MuInvestigationDialog._tab_index(dialog, name)
        dialog._field_widget = lambda field: MuInvestigationDialog._field_widget(dialog, field)
        dialog._focus_widget = lambda widget: MuInvestigationDialog._focus_widget(dialog, widget)

        MuInvestigationDialog.navigate_to(dialog, "Zjištění", "ishikawa")
        self.assertEqual(
            self.widget.inner_tabs.tabText(self.widget.inner_tabs.currentIndex()),
            INNER_TAB_HYPOTHESES,
        )

        MuInvestigationDialog.navigate_to(dialog, "Zjištění", "zjištění")
        self.assertEqual(
            self.widget.inner_tabs.tabText(self.widget.inner_tabs.currentIndex()),
            INNER_TAB_FINDINGS,
        )


if __name__ == "__main__":
    unittest.main()
