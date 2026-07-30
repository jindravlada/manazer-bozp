"""MU-UX-6 – logické oblasti záložky Dodržování předpisů (nyní jako podzáložky)."""

from __future__ import annotations

import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QPushButton

from moduly.vysetrovani_mu.ui.mu_dodrzovani_predpisu_widget import (
    MuDodrzovaniPredpisuWidget,
    _TAB_TITLES,
)

_EXPECTED_KEYS = {
    "dodrz_pracovni_doba",
    "dodrz_prescasy",
    "dodrz_prescasy_detail",
    "dodrz_predpisy_cinnost",
    "dodrz_oopp_rows",
    "dodrz_skoleni_rows",
    "dodrz_lekar_typ",
    "dodrz_lekar_datum",
    "dodrz_lekar_platnost",
    "dodrz_kvalifikace_splnuje",
    "dodrz_kvalifikace_poznamka",
    "dodrz_kontroly_reviz_zavady",
    "dodrz_zkousky_rows",
    "dodrz_ostatni_1",
    "dodrz_oopp_pouzity",
    "dodrz_stav_oopp",
    "dodrz_vyjadreni_oopp",
    "dodrz_kontrola_oopp_rows",
    "dodrz_kontrola_predpisu_rows",
    "dodrz_poruseni_predpisu",
    "dodrz_ostatni_2",
    "dodrz_priloha",
}


class MuUx6DodrzovaniLayoutTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.widget = MuDodrzovaniPredpisuWidget()

    def tearDown(self) -> None:
        self.widget.close()
        self.widget.deleteLater()

    def _tab_titles(self) -> list[str]:
        return [self.widget.inner_tabs.tabText(i) for i in range(self.widget.inner_tabs.count())]

    def test_four_investigation_blocks_in_order(self) -> None:
        self.assertEqual(self._tab_titles(), list(_TAB_TITLES))

    def test_ostatni_is_in_last_block(self) -> None:
        self.assertEqual(self._tab_titles()[-1], "Další skutečnosti")
        groups = [g.title() for g in self.widget.findChildren(QGroupBox)]
        self.assertIn("Záznamy k předpisům", groups)
        self.assertIn("Záznamy k osobě a OOPP", groups)

    def test_lekar_inside_odborna_zpusobilost(self) -> None:
        groups = [g.title() for g in self.widget.findChildren(QGroupBox)]
        self.assertIn("Lékařská prohlídka", groups)
        self.assertIn("Kvalifikace", groups)
        self.assertNotIn("Lékařská prohlídka", self._tab_titles())

    def test_vyjadreni_after_stav_oopp(self) -> None:
        groups = [g.title() for g in self.widget.findChildren(QGroupBox)]
        stav = groups.index("Stav OOPP")
        vyj = groups.index("Vyjádření zaměstnance")
        self.assertEqual(vyj, stav + 1)

    def test_get_data_keys_unchanged(self) -> None:
        self.assertEqual(set(self.widget.get_data().keys()), _EXPECTED_KEYS)

    def test_edit_save_load_roundtrip(self) -> None:
        self.widget.dodrz_predpisy_cinnost.setPlainText("NV 361/2007")
        self.widget.dodrz_poruseni_predpisu.setPlainText("Porušení PP")
        self.widget.dodrz_oopp_rows[0]["typ"].setText("Helma")
        self.widget.dodrz_skoleni_rows[0]["typ"].setText("BOZP")
        self.widget.dodrz_zkousky_rows[0]["typ"].setText("Jeřábník")
        self.widget.dodrz_vyjadreni_oopp.setPlainText("Použil jsem OOPP")
        self.widget.dodrz_ostatni_1.setPlainText("Poznámka A")
        self.widget.dodrz_ostatni_2.setPlainText("Poznámka B")
        self.widget.dodrz_stav_oopp.setPlainText("Neponičeno")
        self.widget.dodrz_kontroly_reviz_zavady.setPlainText("Bez závad")
        self.widget.dodrz_kvalifikace_poznamka.setPlainText("OK")
        payload = self.widget.get_json()

        other = MuDodrzovaniPredpisuWidget()
        try:
            other.load_json(payload)
            data = other.get_data()
            self.assertEqual(data["dodrz_predpisy_cinnost"], "NV 361/2007")
            self.assertEqual(data["dodrz_poruseni_predpisu"], "Porušení PP")
            self.assertEqual(data["dodrz_oopp_rows"][0]["typ"], "Helma")
            self.assertEqual(data["dodrz_skoleni_rows"][0]["typ"], "BOZP")
            self.assertEqual(data["dodrz_zkousky_rows"][0]["typ"], "Jeřábník")
            self.assertEqual(data["dodrz_vyjadreni_oopp"], "Použil jsem OOPP")
            self.assertEqual(data["dodrz_ostatni_1"], "Poznámka A")
            self.assertEqual(data["dodrz_ostatni_2"], "Poznámka B")
            self.assertEqual(data["dodrz_stav_oopp"], "Neponičeno")
            self.assertEqual(data["dodrz_kontroly_reviz_zavady"], "Bez závad")
            self.assertEqual(data["dodrz_kvalifikace_poznamka"], "OK")
            self.assertEqual(set(data.keys()), _EXPECTED_KEYS)
        finally:
            other.close()
            other.deleteLater()

    def test_dynamic_lists_add_and_remove(self) -> None:
        self.assertEqual(len(self.widget.dodrz_oopp_rows), 1)
        self.widget.add_dodrz_oopp_row()
        self.widget.dodrz_oopp_rows[0]["typ"].setText("A")
        self.widget.dodrz_oopp_rows[1]["typ"].setText("B")
        self.assertEqual(len(self.widget.dodrz_oopp_rows), 2)

        self.widget._remove_dynamic_row(
            self.widget.dodrz_oopp_rows,
            0,
            self.widget.dodrz_oopp_rows_layout,
        )
        self.assertEqual(len(self.widget.dodrz_oopp_rows), 1)
        self.assertEqual(self.widget.dodrz_oopp_rows[0]["typ"].text(), "B")

        self.widget.add_dodrz_skoleni_row()
        self.widget.add_dodrz_zkouska_row()
        self.assertEqual(len(self.widget.dodrz_skoleni_rows), 2)
        self.assertEqual(len(self.widget.dodrz_zkousky_rows), 2)

    def test_add_buttons_present(self) -> None:
        labels = {btn.text() for btn in self.widget.findChildren(QPushButton)}
        self.assertIn("Přidat OOPP", labels)
        self.assertIn("Přidat školení", labels)
        self.assertIn("Přidat zkoušku", labels)

    def test_resize_usable(self) -> None:
        for width, height in ((420, 640), (900, 800), (1400, 1000)):
            self.widget.resize(width, height)
            self.assertTrue(self.widget.dodrz_predpisy_cinnost.isEnabled())
            self.assertTrue(self.widget.dodrz_oopp_rows[0]["typ"].isEnabled())
            self.assertEqual(self._tab_titles(), list(_TAB_TITLES))

    def test_json_shape_stable_for_export(self) -> None:
        raw = json.loads(self.widget.get_json())
        self.assertEqual(set(raw.keys()), _EXPECTED_KEYS)
        self.assertIsInstance(raw["dodrz_oopp_rows"], list)
        self.assertIsInstance(raw["dodrz_skoleni_rows"], list)
        self.assertIsInstance(raw["dodrz_zkousky_rows"], list)
        self.assertIsInstance(raw["dodrz_kontrola_oopp_rows"], list)
        self.assertIsInstance(raw["dodrz_kontrola_predpisu_rows"], list)


if __name__ == "__main__":
    unittest.main()
