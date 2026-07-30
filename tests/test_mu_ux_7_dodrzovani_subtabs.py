"""MU-UX-7 – podzáložky a kompaktní dynamické seznamy Dodržování předpisů."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QLabel,
    QPushButton,
    QTabWidget,
    QWidget,
)

from moduly.vysetrovani_mu.ui.mu_dodrzovani_predpisu_widget import (
    TAB_DALSI,
    TAB_ODBORNA,
    TAB_OOPP,
    TAB_PREDPISY,
    MuDodrzovaniPredpisuWidget,
    _KONTROLA_HEADERS,
    _OOPP_HEADERS,
    _SKOLENI_HEADERS,
    _TAB_TITLES,
    _ZKOUSKY_HEADERS,
)


def _header_texts(outer_layout) -> list[str]:
    header = outer_layout.itemAt(0).widget()
    layout = header.layout()
    return [
        layout.itemAt(i).widget().text()
        for i in range(layout.count())
        if layout.itemAt(i).widget() and layout.itemAt(i).widget().text()
    ]


class MuUx7DodrzovaniSubtabsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.widget = MuDodrzovaniPredpisuWidget()
        self.widget.resize(1100, 800)
        self.widget.show()

    def tearDown(self) -> None:
        self.widget.close()
        self.widget.deleteLater()

    def test_four_subtabs_exist(self) -> None:
        tabs = self.widget.inner_tabs
        self.assertIsInstance(tabs, QTabWidget)
        self.assertEqual(tabs.count(), 4)
        self.assertEqual(
            [tabs.tabText(i) for i in range(4)],
            list(_TAB_TITLES),
        )

    def test_fields_placed_on_expected_tabs(self) -> None:
        self.widget.focus_field("dodrz_predpisy_cinnost")
        self.assertEqual(self.widget.inner_tabs.currentIndex(), TAB_PREDPISY)
        self.widget.focus_field("dodrz_lekar_typ")
        self.assertEqual(self.widget.inner_tabs.currentIndex(), TAB_ODBORNA)
        self.widget.focus_field("dodrz_stav_oopp")
        self.assertEqual(self.widget.inner_tabs.currentIndex(), TAB_OOPP)
        self.widget.focus_field("dodrz_ostatni_1")
        self.assertEqual(self.widget.inner_tabs.currentIndex(), TAB_DALSI)

    def test_save_load_roundtrip(self) -> None:
        self.widget.dodrz_predpisy_cinnost.setPlainText("Předpis X")
        self.widget.dodrz_skoleni_rows[0]["typ"].setText("Školení Y")
        self.widget.dodrz_oopp_rows[0]["typ"].setText("OOPP Z")
        self.widget.dodrz_ostatni_2.setPlainText("Další")
        payload = self.widget.get_json()
        other = MuDodrzovaniPredpisuWidget()
        try:
            other.load_json(payload)
            data = other.get_data()
            self.assertEqual(data["dodrz_predpisy_cinnost"], "Předpis X")
            self.assertEqual(data["dodrz_skoleni_rows"][0]["typ"], "Školení Y")
            self.assertEqual(data["dodrz_oopp_rows"][0]["typ"], "OOPP Z")
            self.assertEqual(data["dodrz_ostatni_2"], "Další")
        finally:
            other.close()
            other.deleteLater()

    def test_add_remove_skoleni(self) -> None:
        self.widget.add_dodrz_skoleni_row()
        self.widget.dodrz_skoleni_rows[0]["typ"].setText("A")
        self.widget.dodrz_skoleni_rows[1]["typ"].setText("B")
        self.assertEqual(len(self.widget.dodrz_skoleni_rows), 2)
        self.widget._remove_dynamic_row(
            self.widget.dodrz_skoleni_rows,
            0,
            self.widget.dodrz_skoleni_rows_layout,
        )
        self.assertEqual(len(self.widget.dodrz_skoleni_rows), 1)
        self.assertEqual(self.widget.dodrz_skoleni_rows[0]["typ"].text(), "B")

    def test_add_remove_zkouska(self) -> None:
        self.widget.add_dodrz_zkouska_row()
        self.assertEqual(len(self.widget.dodrz_zkousky_rows), 2)
        self.widget._remove_dynamic_row(
            self.widget.dodrz_zkousky_rows,
            1,
            self.widget.dodrz_zkousky_rows_layout,
        )
        self.assertEqual(len(self.widget.dodrz_zkousky_rows), 1)

    def test_add_remove_oopp(self) -> None:
        self.widget.add_dodrz_oopp_row()
        self.assertEqual(len(self.widget.dodrz_oopp_rows), 2)
        self.widget._remove_dynamic_row(
            self.widget.dodrz_oopp_rows,
            0,
            self.widget.dodrz_oopp_rows_layout,
        )
        self.assertEqual(len(self.widget.dodrz_oopp_rows), 1)

    def test_add_remove_kontrola(self) -> None:
        self.widget.add_dodrz_kontrola_predpisu_row()
        self.widget.add_dodrz_kontrola_oopp_row()
        self.assertEqual(len(self.widget.dodrz_kontrola_predpisu_rows), 2)
        self.assertEqual(len(self.widget.dodrz_kontrola_oopp_rows), 2)
        self.widget._remove_dynamic_row(
            self.widget.dodrz_kontrola_predpisu_rows,
            0,
            self.widget.dodrz_kontrola_predpisu_rows_layout,
        )
        self.widget._remove_dynamic_row(
            self.widget.dodrz_kontrola_oopp_rows,
            0,
            self.widget.dodrz_kontrola_oopp_rows_layout,
        )
        self.assertEqual(len(self.widget.dodrz_kontrola_predpisu_rows), 1)
        self.assertEqual(len(self.widget.dodrz_kontrola_oopp_rows), 1)

    def test_list_headers(self) -> None:
        self.assertEqual(_header_texts(self.widget.dodrz_skoleni_layout), list(_SKOLENI_HEADERS))
        self.assertEqual(_header_texts(self.widget.dodrz_zkousky_layout), list(_ZKOUSKY_HEADERS))
        self.assertEqual(_header_texts(self.widget.dodrz_oopp_layout), list(_OOPP_HEADERS))
        self.assertEqual(
            _header_texts(self.widget.dodrz_kontrola_predpisu_layout),
            list(_KONTROLA_HEADERS),
        )
        self.assertEqual(
            _header_texts(self.widget.dodrz_kontrola_oopp_layout),
            list(_KONTROLA_HEADERS),
        )

    def test_no_empty_left_panel_in_lists(self) -> None:
        for outer in (
            self.widget.dodrz_oopp_layout,
            self.widget.dodrz_skoleni_layout,
            self.widget.dodrz_zkousky_layout,
            self.widget.dodrz_kontrola_predpisu_layout,
        ):
            host = outer.parentWidget()
            self.assertIsNotNone(host)
            # Hlavička je samostatný widget, ne součást datového řádku.
            header = outer.itemAt(0).widget()
            rows_host = outer.itemAt(1).widget()
            self.assertIsNotNone(header)
            self.assertIsNotNone(rows_host)
            self.assertIsNot(header, rows_host)
            self.assertTrue(header.property("muDodrzListHeader"))
            # Žádný prázdný QLabel vlevo v hlavičce.
            first = header.layout().itemAt(0).widget()
            self.assertIsInstance(first, QLabel)
            self.assertTrue(first.text().strip())

    def test_header_not_overlapping_rows(self) -> None:
        self.widget.inner_tabs.setCurrentIndex(TAB_ODBORNA)
        QApplication.processEvents()
        header = self.widget.dodrz_skoleni_layout.itemAt(0).widget()
        rows_host = self.widget.dodrz_skoleni_layout.itemAt(1).widget()
        self.assertGreaterEqual(rows_host.y(), header.y() + header.height() - 2)
        row = rows_host.layout().itemAt(0).widget()
        self.assertIsNotNone(row)
        self.assertTrue(row.property("muDodrzListRow"))
        # Hlavička a řádek mají stejný počet sloupců.
        self.assertEqual(header.layout().count(), row.layout().count())

    def test_focus_field_switches_subtab(self) -> None:
        self.widget.inner_tabs.setCurrentIndex(TAB_PREDPISY)
        focused = self.widget.focus_field("dodrz_vyjadreni_oopp")
        self.assertEqual(self.widget.inner_tabs.currentIndex(), TAB_OOPP)
        self.assertIs(focused, self.widget.dodrz_vyjadreni_oopp)

    def test_dialog_navigation_to_subtab(self) -> None:
        from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog

        dialog = MagicMock()
        dialog.tabs = QTabWidget()
        dialog.tabs.addTab(QWidget(), "Dodržování předpisů")
        dialog.dodrzovani_predpisu_widget = self.widget
        dialog._tab_index = lambda name: MuInvestigationDialog._tab_index(dialog, name)
        dialog._field_widget = lambda field: MuInvestigationDialog._field_widget(dialog, field)
        dialog._focus_widget = lambda widget: MuInvestigationDialog._focus_widget(dialog, widget)

        MuInvestigationDialog.navigate_to(dialog, "Dodržování předpisů", "dodrz_lekar_datum")
        self.assertEqual(dialog.tabs.currentIndex(), 0)
        self.assertEqual(self.widget.inner_tabs.currentIndex(), TAB_ODBORNA)

    def test_export_keys_unchanged(self) -> None:
        data = json.loads(self.widget.get_json())
        self.assertIn("dodrz_predpisy_cinnost", data)
        self.assertIn("dodrz_oopp_rows", data)
        self.assertIn("dodrz_skoleni_rows", data)
        self.assertIn("dodrz_zkousky_rows", data)
        self.assertIn("dodrz_kontrola_oopp_rows", data)
        self.assertIn("dodrz_kontrola_predpisu_rows", data)
        self.assertIn("dodrz_priloha", data)

    def test_scroll_position_preserved_per_tab(self) -> None:
        from PySide6.QtTest import QTest

        self.widget.inner_tabs.setCurrentIndex(TAB_PREDPISY)
        self.widget._active_scroll_tab = TAB_PREDPISY
        bar_predpisy = self.widget._tab_scrolls[TAB_PREDPISY].verticalScrollBar()
        saved = bar_predpisy.value()
        self.widget._on_inner_tab_changed(TAB_OOPP)
        self.assertEqual(self.widget._tab_scroll_positions.get(TAB_PREDPISY), saved)

        # Návrat na Předpisy obnoví uloženou pozici.
        self.widget._tab_scroll_positions[TAB_PREDPISY] = saved
        self.widget._active_scroll_tab = TAB_OOPP
        self.widget._on_inner_tab_changed(TAB_PREDPISY)
        QTest.qWait(30)
        self.assertEqual(bar_predpisy.value(), saved)

    def test_oopp_group_order(self) -> None:
        titles = [g.title() for g in self.widget.findChildren(QGroupBox)]
        expected = [
            "Přidělené OOPP",
            "Používání OOPP při události",
            "Stav OOPP",
            "Vyjádření zaměstnance",
            "Kontrola OOPP",
        ]
        positions = [titles.index(t) for t in expected]
        self.assertEqual(positions, sorted(positions))

    def test_remove_buttons_present(self) -> None:
        labels = {btn.text() for btn in self.widget.findChildren(QPushButton)}
        self.assertIn("Odebrat", labels)
        self.assertIn("Přidat kontrolu", labels)


if __name__ == "__main__":
    unittest.main()
