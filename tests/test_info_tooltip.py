import unittest

from core.widgets.info_tooltip import (
    DEFAULT_TOOLTIP_MAX_WIDTH,
    format_info_card,
    wrap_tooltip_text,
)


class InfoTooltipTests(unittest.TestCase):
    def test_wrap_tooltip_text_breaks_long_line(self) -> None:
        text = "word " * 30
        wrapped = wrap_tooltip_text(text.strip(), max_width=20)
        lines = [line for line in wrapped.split("\n") if line]

        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(len(line), 20)

    def test_format_info_card_wraps_note(self) -> None:
        note = "Velmi dlouhý popis úrazového děje, který by se jinak roztáhl přes celou obrazovku bez zalamování."
        card = format_info_card(
            title="Pracovní úraz",
            rows=[("Zaměstnanec:", "Jan Novák")],
            note=note,
            max_width=40,
        )

        self.assertIn("Poznámka:", card)
        note_lines = card.split("Poznámka:\n", 1)[1].split("\n")
        self.assertGreater(len(note_lines), 1)
        for line in note_lines:
            if line:
                self.assertLessEqual(len(line), 40)

    def test_format_info_card_wraps_row_value(self) -> None:
        card = format_info_card(
            title="Úkol",
            rows=[("Popis:", "A" * 120)],
            max_width=DEFAULT_TOOLTIP_MAX_WIDTH,
        )

        self.assertIn("Popis:", card)
        self.assertGreater(card.count("\n"), 2)


if __name__ == "__main__":
    unittest.main()
