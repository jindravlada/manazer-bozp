"""MU-UX-5 – popisky polí na záložce Dodržování předpisů."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QWidget

from moduly.vysetrovani_mu.ui.mu_dodrzovani_predpisu_widget import (
    MuDodrzovaniPredpisuWidget,
    _KONTROLA_HEADERS,
    _OOPP_HEADERS,
    _SKOLENI_HEADERS,
    _ZKOUSKY_HEADERS,
)


def _header_widget(outer_layout) -> QWidget:
    header = outer_layout.itemAt(0).widget()
    assert header is not None
    return header


def _header_texts(outer_layout) -> list[str]:
    header = _header_widget(outer_layout)
    texts: list[str] = []
    layout = header.layout()
    assert layout is not None
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        assert isinstance(widget, QLabel)
        if widget.text():
            texts.append(widget.text())
    return texts


def _first_data_row(outer_layout) -> QWidget:
    rows_host = outer_layout.itemAt(1).widget()
    assert rows_host is not None
    rows_layout = rows_host.layout()
    assert rows_layout is not None
    row = rows_layout.itemAt(0).widget()
    assert row is not None
    return row


class MuUx5DodrzovaniLabelsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.widget = MuDodrzovaniPredpisuWidget()

    def tearDown(self) -> None:
        self.widget.close()
        self.widget.deleteLater()

    def test_oopp_column_labels_visible(self) -> None:
        self.assertEqual(_header_texts(self.widget.dodrz_oopp_layout), list(_OOPP_HEADERS))
        self.assertEqual(_OOPP_HEADERS[0], "Název OOPP")
        self.assertEqual(_OOPP_HEADERS[-1], "Akce")

    def test_skoleni_column_labels_and_success_radio(self) -> None:
        self.assertEqual(
            _header_texts(self.widget.dodrz_skoleni_layout),
            list(_SKOLENI_HEADERS),
        )
        self.assertIn("Úspěšně absolvováno", _SKOLENI_HEADERS)
        row = self.widget.dodrz_skoleni_rows[0]
        self.assertEqual(row["osnova"].toolTip(), "Úspěšně absolvováno")
        from PySide6.QtWidgets import QRadioButton

        labels = [btn.text() for btn in row["osnova"].findChildren(QRadioButton)]
        self.assertEqual(labels, ["ANO", "NE"])

    def test_zkousky_column_labels_visible(self) -> None:
        self.assertEqual(
            _header_texts(self.widget.dodrz_zkousky_layout),
            list(_ZKOUSKY_HEADERS),
        )
        self.assertEqual(_ZKOUSKY_HEADERS[1], "Platnost od")
        self.assertEqual(_ZKOUSKY_HEADERS[2], "Platnost do")

    def test_vyjadreni_has_field_label(self) -> None:
        label: QLabel | None = None
        for candidate in self.widget.findChildren(QLabel):
            if candidate.text() == "Vyjádření / stanovisko:":
                label = candidate
                break
        self.assertIsNotNone(label)
        self.assertIsNotNone(self.widget.dodrz_vyjadreni_oopp)
        self.assertTrue(self.widget.dodrz_vyjadreni_oopp.isEnabled())

    def test_kontrola_headers_visible(self) -> None:
        self.assertEqual(
            _header_texts(self.widget.dodrz_kontrola_oopp_layout),
            list(_KONTROLA_HEADERS),
        )
        self.assertEqual(
            _header_texts(self.widget.dodrz_kontrola_predpisu_layout),
            list(_KONTROLA_HEADERS),
        )

    def test_add_row_keeps_header_and_alignment(self) -> None:
        before = _header_texts(self.widget.dodrz_oopp_layout)
        self.widget.add_dodrz_oopp_row()
        self.widget.add_dodrz_skoleni_row()
        self.widget.add_dodrz_zkouska_row()
        self.assertEqual(_header_texts(self.widget.dodrz_oopp_layout), before)
        self.assertEqual(len(self.widget.dodrz_oopp_rows), 2)
        # Hlavička + kontejner řádků + tlačítko
        self.assertEqual(self.widget.dodrz_oopp_layout.count(), 3)
        header = _header_widget(self.widget.dodrz_oopp_layout)
        data_row = _first_data_row(self.widget.dodrz_oopp_layout)
        self.assertEqual(data_row.layout().count(), header.layout().count())
        for index in range(header.layout().count()):
            self.assertEqual(
                data_row.layout().stretch(index),
                header.layout().stretch(index),
            )

    def test_reload_preserves_headers(self) -> None:
        self.widget.load_json(
            '{"dodrz_oopp_rows":[{"typ":"Helma","datum":"","platnost":"","poznamka":""}],'
            '"dodrz_skoleni_rows":[{}],"dodrz_zkousky_rows":[{}]}'
        )
        self.assertEqual(_header_texts(self.widget.dodrz_oopp_layout), list(_OOPP_HEADERS))
        self.assertEqual(_header_texts(self.widget.dodrz_skoleni_layout), list(_SKOLENI_HEADERS))
        self.assertEqual(_header_texts(self.widget.dodrz_zkousky_layout), list(_ZKOUSKY_HEADERS))

    def test_save_roundtrip_unchanged_keys(self) -> None:
        self.widget.dodrz_oopp_rows[0]["typ"].setText("Rukavice")
        data = self.widget.get_data()
        self.assertIn("typ", data["dodrz_oopp_rows"][0])
        self.assertIn("datum", data["dodrz_oopp_rows"][0])
        self.assertIn("platnost", data["dodrz_oopp_rows"][0])
        self.assertIn("poznamka", data["dodrz_oopp_rows"][0])
        self.assertIn("osnova", data["dodrz_skoleni_rows"][0])
        self.assertIsInstance(data["dodrz_vyjadreni_oopp"], str)

    def test_resize_keeps_labels_readable(self) -> None:
        self.widget.resize(480, 700)
        self.widget.resize(1100, 900)
        for text in _OOPP_HEADERS:
            self.assertTrue(any(lbl.text() == text for lbl in self.widget.findChildren(QLabel)))
        self.assertTrue(self.widget.dodrz_oopp_rows[0]["typ"].isEnabled())
        self.assertIsInstance(self.widget.dodrz_oopp_rows[0]["typ"], QLineEdit)


if __name__ == "__main__":
    unittest.main()
