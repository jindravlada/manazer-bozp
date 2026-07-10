import os
import unittest

from PySide6.QtWidgets import QApplication, QGroupBox

from moduly.sprava_dat.ui.ui_styles import (
    SECTION_HEADING_FONT_SIZE_PX,
    apply_card_group_style,
)


class SectionHeadingStyleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_section_heading_is_larger_than_base_text(self) -> None:
        self.assertEqual(SECTION_HEADING_FONT_SIZE_PX, 17)

    def test_apply_card_group_style_sets_bold_larger_font(self) -> None:
        group = QGroupBox("Kompletní záloha programu")
        apply_card_group_style(group)
        style = group.styleSheet()
        self.assertIn("font-weight: 700", style)
        self.assertIn("font-size: 17px", style)
        self.assertIn("left: 10px", style)


if __name__ == "__main__":
    unittest.main()
