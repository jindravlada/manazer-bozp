"""Nepovinná platnost školení a nápověda u zkoušek (Vyšetřování MU 4.2.2)."""

from __future__ import annotations

import json
import os
import unittest
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from moduly.vysetrovani_mu.ui.mu_dodrzovani_predpisu_widget import (
    MuDodrzovaniPredpisuWidget,
    _ZKOUSKA_PLATNOST_HINT,
)


class MuSkoleniPlatnost422TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.widget = MuDodrzovaniPredpisuWidget()

    def tearDown(self) -> None:
        self.widget.close()
        self.widget.deleteLater()
        self.app.processEvents()

    def _reload(self, raw: str) -> MuDodrzovaniPredpisuWidget:
        other = MuDodrzovaniPredpisuWidget()
        other.load_json(raw)
        self.addCleanup(other.close)
        self.addCleanup(other.deleteLater)
        return other

    def test_skoleni_saves_filled_and_empty_validity(self) -> None:
        filled = self.widget.dodrz_skoleni_rows[0]
        filled["typ"].setText("BOZP")
        filled["datum"].set_date_value(date(2026, 3, 1))
        filled["platnost"].set_date_value(date(2028, 3, 1))
        filled["poznamka"].setText("základní")
        self.widget._set_radio_choice(filled["osnova"], "ANO")
        self.widget.add_dodrz_skoleni_row()
        empty = self.widget.dodrz_skoleni_rows[1]
        empty["typ"].setText("Požární ochrana")
        empty["datum"].set_date_value(date(2026, 4, 2))

        payload = self.widget.get_json()
        loaded = self._reload(payload)
        first = loaded.get_data()["dodrz_skoleni_rows"][0]
        second = loaded.get_data()["dodrz_skoleni_rows"][1]
        self.assertEqual(first["typ"], "BOZP")
        self.assertEqual(first["datum"], "2026-03-01")
        self.assertEqual(first["platnost"], "2028-03-01")
        self.assertEqual(first["osnova"], "ANO")
        self.assertEqual(first["poznamka"], "základní")
        self.assertEqual(loaded.dodrz_skoleni_rows[0]["platnost"].get_date(), date(2028, 3, 1))
        self.assertEqual(second["typ"], "Požární ochrana")
        self.assertEqual(second["datum"], "2026-04-02")
        self.assertEqual(second["platnost"], "")
        self.assertIsNone(loaded.dodrz_skoleni_rows[1]["platnost"].get_date())

    def test_old_skoleni_without_platnost_key_stays_unchanged(self) -> None:
        raw = json.dumps(
            {
                "dodrz_skoleni_rows": [
                    {
                        "typ": "Jeřábnický průkaz",
                        "datum": "2020-05-05",
                        "osnova": "NE",
                        "poznamka": "starý zápis",
                    }
                ],
                "dodrz_zkousky_rows": [
                    {
                        "typ": "Svářeč",
                        "datum": "2019-01-01",
                        "platnost": "2999-12-31",
                        "poznamka": "bez omezení zapsané rokem",
                    }
                ],
            },
            ensure_ascii=False,
        )
        loaded = self._reload(raw)
        row = loaded.dodrz_skoleni_rows[0]
        self.assertEqual(row["typ"].text(), "Jeřábnický průkaz")
        self.assertEqual(row["datum"].get_date(), date(2020, 5, 5))
        self.assertIsNone(row["platnost"].get_date())
        self.assertEqual(row["poznamka"].text(), "starý zápis")
        saved = loaded.get_data()
        skoleni = saved["dodrz_skoleni_rows"][0]
        self.assertEqual(skoleni["typ"], "Jeřábnický průkaz")
        self.assertEqual(skoleni["datum"], "2020-05-05")
        self.assertEqual(skoleni["osnova"], "NE")
        self.assertEqual(skoleni["poznamka"], "starý zápis")
        self.assertEqual(skoleni["platnost"], "")
        zkouska = saved["dodrz_zkousky_rows"][0]
        self.assertEqual(zkouska["typ"], "Svářeč")
        self.assertEqual(zkouska["datum"], "2019-01-01")
        self.assertEqual(zkouska["platnost"], "2999-12-31")
        self.assertEqual(zkouska["poznamka"], "bez omezení zapsané rokem")
        self.assertEqual(loaded.dodrz_zkousky_rows[0]["platnost"].get_date(), date(2999, 12, 31))
        self.assertNotIn('"platnost": "2999-12-31"', raw[raw.find("dodrz_skoleni_rows"):raw.find("dodrz_zkousky_rows")])

    def test_zkouska_hint_is_visible_and_does_not_change_storage(self) -> None:
        texts = [label.text() for label in self.widget.findChildren(QLabel)]
        self.assertIn(_ZKOUSKA_PLATNOST_HINT, texts)
        header = self.widget.dodrz_zkousky_layout.itemAt(0).widget()
        header_label = next(
            label
            for label in header.findChildren(QLabel)
            if label.text() == "Platnost do"
        )
        field = self.widget.dodrz_zkousky_rows[0]["platnost"]
        self.assertEqual(header_label.toolTip(), _ZKOUSKA_PLATNOST_HINT)
        self.assertEqual(field.toolTip(), _ZKOUSKA_PLATNOST_HINT)
        before = {
            "typ": "Jeřábník",
            "datum": "2024-06-01",
            "platnost": "2027-06-01",
            "poznamka": "periodická",
        }
        row = self.widget.dodrz_zkousky_rows[0]
        row["typ"].setText(before["typ"])
        row["datum"].set_date_value(date(2024, 6, 1))
        row["platnost"].set_date_value(date(2027, 6, 1))
        row["poznamka"].setText(before["poznamka"])
        self.assertEqual(self.widget.get_data()["dodrz_zkousky_rows"][0], before)
