"""SEC-HARDENING-ODT-1: aktivní obsah z ODT šablony se do exportu nepřenáší."""

from __future__ import annotations

import shutil
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from PIL import Image

from core.export.odt_engine import (
    OdtExportEngine,
    OdtParagraph,
    OdtRichContent,
    is_active_odt_zip_entry,
)

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "sec-hardening-odt-1"

_CONTENT = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<office:document-content '
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0">'
    "<office:automatic-styles/>"
    "<office:body><office:text>"
    "<text:p>${body}</text:p>"
    "</office:text></office:body></office:document-content>"
)
_STYLES = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<office:document-styles '
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
    "<office:master-styles>"
    '<style:master-page style:name="Standard">'
    "<style:header><text:p>Hlavička test</text:p></style:header>"
    "<style:footer><text:p>Patička test</text:p></style:footer>"
    "</style:master-page>"
    "</office:master-styles>"
    "</office:document-styles>"
)
_MANIFEST = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<manifest:manifest '
    'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">'
    '<manifest:file-entry manifest:full-path="/" '
    'manifest:media-type="application/vnd.oasis.opendocument.text"/>'
    '<manifest:file-entry manifest:full-path="content.xml" '
    'manifest:media-type="text/xml"/>'
    '<manifest:file-entry manifest:full-path="styles.xml" '
    'manifest:media-type="text/xml"/>'
    '<manifest:file-entry manifest:full-path="Basic/" '
    'manifest:media-type="application/binary"/>'
    '<manifest:file-entry manifest:full-path="Basic/Standard/script.xlb" '
    'manifest:media-type="text/xml"/>'
    '<manifest:file-entry manifest:full-path="Scripts/python/macro.py" '
    'manifest:media-type="text/plain"/>'
    '<manifest:file-entry manifest:full-path="Object 1/" '
    'manifest:media-type="application/vnd.oasis.opendocument.ole-object"/>'
    '<manifest:file-entry manifest:full-path="ObjectReplacements/Object 1" '
    'manifest:media-type="image/png"/>'
    "</manifest:manifest>"
)


def _write_template(path: Path, *, with_active: bool) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        archive.writestr("content.xml", _CONTENT)
        archive.writestr("styles.xml", _STYLES)
        archive.writestr("META-INF/manifest.xml", _MANIFEST if with_active else (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<manifest:manifest '
            'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">'
            '<manifest:file-entry manifest:full-path="/" '
            'manifest:media-type="application/vnd.oasis.opendocument.text"/>'
            '<manifest:file-entry manifest:full-path="content.xml" '
            'manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="styles.xml" '
            'manifest:media-type="text/xml"/>'
            "</manifest:manifest>"
        ))
        if with_active:
            archive.writestr("Basic/", b"")
            archive.writestr("Basic/Standard/script.xlb", "<library/>")
            archive.writestr("Scripts/python/macro.py", "print('pwn')\n")
            archive.writestr("Object 1/", b"")
            archive.writestr("Object 1/content.xml", "<ole/>")
            archive.writestr("ObjectReplacements/Object 1", b"\x89PNG\r\n")


class SecHardeningOdt1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        if _TEST_ROOT.exists():
            shutil.rmtree(_TEST_ROOT)
        _TEST_ROOT.mkdir(parents=True)
        self.tmp = _TEST_ROOT / "work"
        self.tmp.mkdir()
        self.engine = OdtExportEngine()

    def tearDown(self) -> None:
        shutil.rmtree(_TEST_ROOT, ignore_errors=True)

    def _render(self, template: Path, values: dict, name: str = "out.odt") -> Path:
        output = self.tmp / name
        return self.engine.render(template, output, values)

    def test_a_basic_macros_are_stripped(self) -> None:
        template = self.tmp / "with-basic.odt"
        _write_template(template, with_active=True)
        path = self._render(template, {"body": "text"}, "a.odt")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
        self.assertFalse(any(is_active_odt_zip_entry(name) for name in names))
        self.assertFalse(any(name.startswith("Basic") for name in names))

    def test_b_scripts_are_stripped(self) -> None:
        template = self.tmp / "with-scripts.odt"
        _write_template(template, with_active=True)
        path = self._render(template, {"body": "text"}, "b.odt")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            manifest = archive.read("META-INF/manifest.xml").decode("utf-8")
        self.assertFalse(any(name.startswith("Scripts/") for name in names))
        self.assertNotIn("Scripts/", manifest)

    def test_c_ole_object_and_manifest_are_stripped(self) -> None:
        template = self.tmp / "with-ole.odt"
        _write_template(template, with_active=True)
        path = self._render(template, {"body": "text"}, "c.odt")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            manifest = archive.read("META-INF/manifest.xml").decode("utf-8")
        self.assertFalse(any(name.startswith("Object 1") for name in names))
        self.assertFalse(any(name.startswith("ObjectReplacements/") for name in names))
        self.assertNotIn('manifest:full-path="Object 1/', manifest)
        self.assertNotIn("ole-object", manifest)
        self.assertNotIn("ObjectReplacements/", manifest)
        self.assertNotIn('manifest:full-path="Basic/"', manifest)

    def test_d_plain_odt_stays_functional(self) -> None:
        template = self.tmp / "plain.odt"
        _write_template(template, with_active=False)
        path = self._render(template, {"body": "Funkční text"}, "d.odt")
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            content = archive.read("content.xml").decode("utf-8")
            styles = archive.read("styles.xml").decode("utf-8")
        self.assertEqual(
            names,
            {"mimetype", "content.xml", "styles.xml", "META-INF/manifest.xml"},
        )
        self.assertIn("Funkční text", content)
        self.assertIn("Hlavička test", styles)
        self.assertIn("Patička test", styles)

    def test_e_legit_image_paragraph_remains(self) -> None:
        template = self.tmp / "img-template.odt"
        _write_template(template, with_active=True)
        photo = self.tmp / "photo.jpg"
        Image.new("RGB", (40, 24), color=(10, 80, 160)).save(photo, format="JPEG")
        photo_bytes = photo.read_bytes()
        path = self._render(
            template,
            {"body": OdtRichContent(paragraphs=[OdtParagraph.image(photo)])},
            "e.odt",
        )
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            pictures = [n for n in names if n.startswith("Pictures/")]
            self.assertEqual(len(pictures), 1)
            self.assertEqual(archive.read(pictures[0]), photo_bytes)
            content = archive.read("content.xml").decode("utf-8")
            manifest = archive.read("META-INF/manifest.xml").decode("utf-8")
        self.assertIn("draw:image", content)
        self.assertIn(pictures[0], content)
        self.assertIn(pictures[0], manifest)
        self.assertFalse(any(n.startswith("Basic/") for n in names))

    def test_f_content_and_styles_remain_valid_xml(self) -> None:
        template = self.tmp / "valid.odt"
        _write_template(template, with_active=True)
        path = self._render(template, {"body": "A < B"}, "f.odt")
        with zipfile.ZipFile(path) as archive:
            content = archive.read("content.xml")
            styles = archive.read("styles.xml")
            manifest = archive.read("META-INF/manifest.xml")
        ET.fromstring(content)
        ET.fromstring(styles)
        ET.fromstring(manifest)
        self.assertIn("A &lt; B", content.decode("utf-8"))
        self.assertIn("Hlavička test", styles.decode("utf-8"))
        self.assertIn("Patička test", styles.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
