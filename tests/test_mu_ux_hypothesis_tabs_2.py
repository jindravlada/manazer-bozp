"""MU-UX-HYPOTHESIS-TABS-2 – Hypotézy a Zjištění jako hlavní záložky."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QTabWidget, QWidget

from moduly.vysetrovani_mu.sluzby.mu_investigation_check import _CHECK_NAVIGATION, _navigation_for
from moduly.vysetrovani_mu.ui.mu_findings_widget import MuFindingsWidget
from moduly.vysetrovani_mu.ui.mu_ishikawa_widget import MuIshikawaWidget


class MuUxHypothesisTabs2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_findings_widget_has_no_inner_tabs(self) -> None:
        widget = MuFindingsWidget()
        try:
            self.assertFalse(hasattr(widget, "inner_tabs"))
            self.assertFalse(hasattr(widget, "ishikawa_widget"))
            labels = {btn.text() for btn in widget.findChildren(QPushButton)}
            self.assertIn("Přidat", labels)
            self.assertIn("Upravit", labels)
            self.assertIn("Smazat", labels)
            self.assertNotIn("Přidat příčinu", labels)
        finally:
            widget.close()
            widget.deleteLater()

    def test_ishikawa_widget_standalone(self) -> None:
        findings = MuFindingsWidget()
        ishikawa = MuIshikawaWidget(on_findings_changed=findings.refresh)
        try:
            labels = {btn.text() for btn in ishikawa.findChildren(QPushButton)}
            self.assertIn("Přidat příčinu", labels)
            self.assertIn("Vytvořit zjištění", labels)
            self.assertIn("Řetězec příčin", labels)
            self.assertEqual(ishikawa._on_findings_changed.__func__, findings.refresh.__func__)
        finally:
            ishikawa.close()
            findings.close()
            ishikawa.deleteLater()
            findings.deleteLater()

    def test_dialog_main_tab_order(self) -> None:
        from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog

        dialog = MuInvestigationDialog()
        try:
            titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
            self.assertIn("Hypotézy", titles)
            self.assertIn("Zjištění", titles)
            self.assertLess(titles.index("Hypotézy"), titles.index("Zjištění"))
            self.assertEqual(titles.index("Zjištění") + 1, titles.index("Závěr"))
            # Mezi Hypotézy a Zjištění zatím není Bariéry – slot je připravený.
            between = titles[titles.index("Hypotézy") + 1 : titles.index("Zjištění")]
            self.assertEqual(between, [])
            self.assertIsInstance(dialog.ishikawa_widget, MuIshikawaWidget)
            self.assertIsInstance(dialog.findings_widget, MuFindingsWidget)
            # Žádné vnitřní podzáložky Hypotézy/Zjištění.
            self.assertFalse(hasattr(dialog.findings_widget, "inner_tabs"))
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_ishikawa_json_roundtrip_via_dialog(self) -> None:
        from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog

        dialog = MuInvestigationDialog()
        try:
            payload = {
                "causes": [
                    {
                        "id": "c1",
                        "category": "Člověk",
                        "description": "Neopatrnost",
                        "status": "hypoteza",
                        "level": "bezprostredni",
                        "factors": [],
                    }
                ]
            }
            dialog.ishikawa_widget.load_json(json.dumps(payload, ensure_ascii=False))
            data = dialog.get_data()
            loaded = json.loads(data["ishikawa_json"])
            self.assertEqual(loaded["causes"][0]["description"], "Neopatrnost")
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_check_navigation_targets_correct_main_tabs(self) -> None:
        self.assertEqual(_CHECK_NAVIGATION["ishikawa.none"], ("Hypotézy", "ishikawa"))
        self.assertEqual(_CHECK_NAVIGATION["ishikawa.rejected_chain"], ("Hypotézy", "ishikawa"))
        self.assertEqual(_CHECK_NAVIGATION["findings.none"], ("Zjištění", "zjištění"))
        self.assertEqual(_navigation_for("ishikawa.status_x", "Zjištění"), ("Hypotézy", "ishikawa"))
        self.assertEqual(
            _navigation_for("findings.responsible_missing_1", "Zjištění"),
            ("Zjištění", "odpovedna_osoba"),
        )

    def test_dialog_navigate_opens_hypotheses_or_findings(self) -> None:
        from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog

        dialog = MuInvestigationDialog()
        try:
            MuInvestigationDialog.navigate_to(dialog, "Hypotézy", "ishikawa")
            self.assertEqual(dialog.tabs.tabText(dialog.tabs.currentIndex()), "Hypotézy")
            MuInvestigationDialog.navigate_to(dialog, "Zjištění", "zjištění")
            self.assertEqual(dialog.tabs.tabText(dialog.tabs.currentIndex()), "Zjištění")
        finally:
            dialog.close()
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
