"""MU-UX-5 – popisky polí na záložce Dodržování předpisů."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QLineEdit

from moduly.vysetrovani_mu.ui.mu_dodrzovani_predpisu_widget import (
    MuDodrzovaniPredpisuWidget,
    _KONTROLA_HEADERS,
    _OOPP_HEADERS,
    _SKOLENI_HEADERS,
    _ZKOUSKY_HEADERS,
)


def _header_texts(layout) -> list[str]:
    header = layout.itemAt(0).layout()
    assert header is not None
    texts: list[str] = []
    for index in range(header.count()):
        widget = header.itemAt(index).widget()
        assert isinstance(widget, QLabel)
        texts.append(widget.text())
    return texts


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
        self.assertEqual(
            _OOPP_HEADERS,
            (
                "Název OOPP",
                "Datum vydání",
                "Datum ukončení používání",
                "Poznámka",
            ),
        )

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
        form = label.parentWidget().layout() if label is not None else None
        self.assertIsInstance(form, QFormLayout)

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
        # Hlavička + 2 řádky + tlačítko
        self.assertEqual(self.widget.dodrz_oopp_layout.count(), 4)
        data_row = self.widget.dodrz_oopp_layout.itemAt(1).layout()
        header = self.widget.dodrz_oopp_layout.itemAt(0).layout()
        self.assertEqual(data_row.count(), header.count())
        for index in range(header.count()):
            self.assertEqual(
                data_row.stretch(index),
                header.stretch(index),
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
        # Popisky nejsou prázdné a pole zůstávají editovatelná.
        self.assertTrue(self.widget.dodrz_oopp_rows[0]["typ"].isEnabled())
        self.assertIsInstance(self.widget.dodrz_oopp_rows[0]["typ"], QLineEdit)


if __name__ == "__main__":
    unittest.main()
