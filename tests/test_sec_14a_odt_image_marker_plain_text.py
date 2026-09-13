"""SEC-14a: běžný text s ODT_IMAGE značkou nesmí načíst soubor."""

from __future__ import annotations

import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from core.export.odt_engine import (
    OdtExportEngine,
    OdtParagraph,
    OdtRichContent,
)

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"
_CANARY_BYTES = b"SEC-14A-CANARY-BYTES-MUST-NOT-APPEAR-IN-ODT"
_MARKER_PATH = "/cesta/k/canary.txt"
_MARKER_TEXT = f"[[[ODT_IMAGE|{_MARKER_PATH}]]]"


def _write_minimal_odt(path: Path) -> None:
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        "<office:body><office:text>"
        "<text:p>${body}</text:p>"
        "<text:p>${escaped}</text:p>"
        "</office:text></office:body></office:document-content>"
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-styles '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"/>'
    )
    meta = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-meta '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"/>'
    )
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest:manifest '
        'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">'
        "</manifest:manifest>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        archive.writestr("content.xml", content)
        archive.writestr("styles.xml", styles)
        archive.writestr("meta.xml", meta)
        archive.writestr("META-INF/manifest.xml", manifest)


class Sec14aOdtImageMarkerPlainTextTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _TEST_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="sec14a-", dir=_TEST_ROOT))
        self.template = self.tmp / "template.odt"
        _write_minimal_odt(self.template)
        self.canary = self.tmp / "canary.txt"
        self.canary.write_bytes(_CANARY_BYTES)
        self.engine = OdtExportEngine()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _render(self, values: dict, name: str = "out.odt") -> Path:
        output = self.tmp / name
        return self.engine.render(self.template, output, values)

    def test_plain_marker_stays_text_and_does_not_embed_canary(self) -> None:
        marker = f"[[[ODT_IMAGE|{self.canary}]]]"
        path = self._render({"body": marker, "escaped": "ok"})
        raw = path.read_bytes()
        self.assertNotIn(_CANARY_BYTES, raw)
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            self.assertFalse(any(item.startswith("Pictures/") for item in names))
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn(str(self.canary), content)
        self.assertIn("[[[ODT_IMAGE|", content)
        self.assertNotIn("draw:image", content)

    def test_documented_absolute_marker_is_literal_text(self) -> None:
        path = self._render({"body": _MARKER_TEXT, "escaped": "ok"})
        with zipfile.ZipFile(path) as archive:
            content = archive.read("content.xml").decode("utf-8")
            names = archive.namelist()
        self.assertIn(_MARKER_TEXT, content)
        self.assertFalse(any(item.startswith("Pictures/") for item in names))

    def test_xml_special_characters_remain_escaped(self) -> None:
        path = self._render({"body": "A < B & C > D", "escaped": "ok"})
        with zipfile.ZipFile(path) as archive:
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn("A &lt; B &amp; C &gt; D", content)
        self.assertNotIn("A < B & C > D", content)

    def test_explicit_image_paragraph_still_embeds_photo(self) -> None:
        photo = self.tmp / "photo.jpg"
        Image.new("RGB", (48, 32), color=(12, 80, 160)).save(photo, format="JPEG")
        photo_bytes = photo.read_bytes()
        path = self._render(
            {
                "body": OdtRichContent(paragraphs=[OdtParagraph.image(photo)]),
                "escaped": "ok",
            },
            name="with-photo.odt",
        )
        with zipfile.ZipFile(path) as archive:
            picture_names = [n for n in archive.namelist() if n.startswith("Pictures/")]
            self.assertEqual(len(picture_names), 1)
            embedded = archive.read(picture_names[0])
            content = archive.read("content.xml").decode("utf-8")
        self.assertEqual(embedded, photo_bytes)
        self.assertIn("draw:image", content)
        self.assertIn(_CANARY_BYTES, self.canary.read_bytes())
        self.assertNotIn(_CANARY_BYTES, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
