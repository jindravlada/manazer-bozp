import unittest

from core.widgets.text_preview import (
    DEFAULT_TEXT_PREVIEW_LENGTH,
    TEXT_PREVIEW_SUFFIX,
    truncate_text_preview,
)


class TextPreviewTestCase(unittest.TestCase):
    def test_short_text_is_not_truncated(self) -> None:
        text = "Zajistit školení zaměstnanců"
        self.assertEqual(truncate_text_preview(text), text)

    def test_long_text_is_truncated_with_suffix(self) -> None:
        text = "Zaměstnavatel stanoví a udržuje systém řízení bezpečnosti a ochrany zdraví při práci v souladu s požadavky zákona a prováděcích předpisů."
        preview = truncate_text_preview(text)

        self.assertEqual(len(preview), DEFAULT_TEXT_PREVIEW_LENGTH + len(TEXT_PREVIEW_SUFFIX))
        self.assertTrue(preview.endswith(TEXT_PREVIEW_SUFFIX))
        self.assertEqual(preview[:-len(TEXT_PREVIEW_SUFFIX)], text[:DEFAULT_TEXT_PREVIEW_LENGTH])

    def test_whitespace_is_normalized_before_truncation(self) -> None:
        text = "První   věta.\n\nDruhá věta."
        self.assertEqual(truncate_text_preview(text), "První věta. Druhá věta.")


if __name__ == "__main__":
    unittest.main()
