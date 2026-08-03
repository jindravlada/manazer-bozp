"""Regrese: hlavní okno musí jít zmenšit pod šířku menších displejů (1600×900)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.windows.main_window import MainWindow

# Po načtení všech modulů nesmí QStackedWidget držet okno nad šířkou 1600×900.
# Tvrdý strop < 1500; praktický cíl ≤ 1200 (normální režim zřetelně užší než maximalizace).
_HARD_MAX_MIN_HINT_WIDTH = 1500
_MAX_MIN_HINT_WIDTH = 1200
_MAX_MIN_HINT_HEIGHT = 650
_TARGET_SIZE = (1100, 650)


class MainWindowMinimumSizeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = MainWindow()

    def tearDown(self) -> None:
        self.window.close()
        self.window.deleteLater()
        self.window = None

    def test_minimum_size_hint_fits_small_display(self) -> None:
        hint = self.window.minimumSizeHint()
        self.assertLess(
            hint.width(),
            _HARD_MAX_MIN_HINT_WIDTH,
            f"minimumSizeHint.width={hint.width()} musí být < {_HARD_MAX_MIN_HINT_WIDTH}",
        )
        self.assertLessEqual(
            hint.width(),
            _MAX_MIN_HINT_WIDTH,
            f"minimumSizeHint.width={hint.width()} je příliš velké pro 1600×900",
        )
        self.assertLessEqual(
            hint.height(),
            _MAX_MIN_HINT_HEIGHT,
            f"minimumSizeHint.height={hint.height()} je příliš velké pro 1600×900",
        )

    def test_window_can_resize_to_target(self) -> None:
        width, height = _TARGET_SIZE
        self.window.show()
        self.window.resize(width, height)
        self._app.processEvents()

        size = self.window.size()
        self.assertEqual(size.width(), width)
        self.assertEqual(size.height(), height)
        self.assertLessEqual(self.window.minimumSize().width(), width)
        self.assertLessEqual(self.window.minimumSize().height(), height)

    def test_default_resize_is_not_minimum(self) -> None:
        """Výchozí resize(1280, 800) nesmí být zároveň minimální velikostí."""
        hint = self.window.minimumSizeHint()
        self.assertLess(hint.width(), 1280)
        self.assertLess(hint.height(), 800)


if __name__ == "__main__":
    unittest.main()
