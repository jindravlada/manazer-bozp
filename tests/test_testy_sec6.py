"""TESTY-SEC-6: import obrázku znovu zakóduje jen obrazové body."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageOps
from PIL.ExifTags import IFD
from PIL.PngImagePlugin import PngInfo

from moduly.testy.sluzby.written_image_normalizer import (
    IMAGE_LOAD_FAILED,
    IMAGE_TOO_LARGE,
    MAX_INPUT_BYTES,
    MAX_STORED_BYTES,
    WrittenImageError,
    normalize_written_image,
)

_TMP = Path(tempfile.mkdtemp(prefix="testy-sec6-"))
_TRAILER = b"ATTACHED-PAYLOAD-SEC6"
_COMMENT = b"komentar-SEC6"
_MAKE = "SecretMakeSEC6"
_GPS_MARK = "GPS-SEC6-MARKER"


class WrittenImageMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        root = _TMP / self._testMethodName
        self.sources = root / "zdroj"
        self.output = root / "vystup"
        self.sources.mkdir(parents=True)
        self.output.mkdir()
        self.kept = self.output / "uz-ulozeny.png"
        self.kept.write_bytes(b"stare-bajty-prilohy")
        self.kept_stamp = self.kept.stat().st_mtime_ns

    def test_plain_png_keeps_pixels_without_original_bytes(self) -> None:
        source = self._png(self.sources / "bezny.png", (80, 40), (20, 90, 160))
        original = source.read_bytes()
        result = normalize_written_image(source, self.output)
        self.assertEqual(result.path.suffix, ".png")
        self.assertEqual((result.width, result.height), (80, 40))
        self.assertLessEqual(result.byte_size, MAX_STORED_BYTES)
        self.assertEqual(self._pixels(result.path), self._pixels(source))
        self.assertEqual(source.read_bytes(), original)
        self._assert_no_metadata(result.path)
        self._assert_kept()

    def test_plain_jpeg_keeps_color_and_drops_container_extras(self) -> None:
        source = self.sources / "bezny.jpg"
        Image.new("RGB", (64, 48), (30, 70, 140)).save(source, "JPEG", quality=90)
        original = source.read_bytes()
        result = normalize_written_image(source, self.output)
        self.assertEqual(result.path.suffix, ".jpg")
        self.assertEqual((result.width, result.height), (64, 48))
        self.assertLessEqual(result.byte_size, MAX_STORED_BYTES)
        self.assertEqual(source.read_bytes(), original)
        self._assert_color(result.path, (30, 70, 140))
        self._assert_no_metadata(result.path)
        self._assert_kept()

    def test_small_png_trailer_and_comment_are_removed(self) -> None:
        source = self._png(self.sources / "maly.png", (16, 12), (240, 20, 20))
        info = PngInfo()
        info.add_text("Comment", _COMMENT.decode("ascii"))
        with Image.open(source) as image:
            image.save(source, "PNG", pnginfo=info)
        source.write_bytes(source.read_bytes() + b"\n" + _TRAILER)
        self.assertIn(_TRAILER, source.read_bytes())
        self.assertLess(source.stat().st_size, MAX_STORED_BYTES)
        result = normalize_written_image(source, self.output)
        stored = result.path.read_bytes()
        self.assertNotIn(_TRAILER, stored)
        self.assertNotIn(_COMMENT, stored)
        self.assertEqual(self._pixels(result.path), self._pattern((16, 12), (240, 20, 20)))
        self.assertLess(result.byte_size, source.stat().st_size)
        self._assert_no_metadata(result.path)
        self._assert_kept()

    def test_exif_and_gps_are_not_stored(self) -> None:
        source = self.sources / "gps.jpg"
        image = Image.new("RGB", (40, 20), (0, 0, 200))
        for x in range(20):
            for y in range(20):
                image.putpixel((x, y), (220, 0, 0))
        exif = Image.Exif()
        exif[271] = _MAKE
        exif[270] = _GPS_MARK
        exif[274] = 2
        gps = exif.get_ifd(IFD.GPSInfo)
        gps[1] = "N"
        gps[2] = (50.0, 1.0)
        gps[3] = "E"
        gps[4] = (14.0, 1.0)
        image.save(source, "JPEG", quality=95, exif=exif, comment=_COMMENT)
        payload = source.read_bytes()
        self.assertIn(_MAKE.encode("ascii"), payload)
        with Image.open(source) as opened:
            self.assertTrue(opened.getexif().get_ifd(IFD.GPSInfo))
            turned = ImageOps.exif_transpose(opened)
            expected_left = self._side_average(turned, "left")
            expected_right = self._side_average(turned, "right")
        result = normalize_written_image(source, self.output)
        stored = result.path.read_bytes()
        self.assertNotIn(_MAKE.encode("ascii"), stored)
        self.assertNotIn(_GPS_MARK.encode("ascii"), stored)
        self.assertNotIn(_COMMENT, stored)
        self.assertEqual((result.width, result.height), (40, 20))
        self._assert_side(result.path, "left", expected_left)
        self._assert_side(result.path, "right", expected_right)
        self._assert_no_metadata(result.path)
        self.assertEqual(source.read_bytes(), payload)
        self._assert_kept()

    def test_transparency_stays_visible(self) -> None:
        source = self.sources / "pruhlednost.png"
        image = Image.new("RGBA", (24, 16), (0, 0, 0, 0))
        for x in range(8, 24):
            for y in range(16):
                image.putpixel((x, y), (180, 40, 20, 255))
        image.save(source, "PNG")
        original = source.read_bytes()
        result = normalize_written_image(source, self.output)
        self.assertEqual(result.path.suffix, ".png")
        self.assertEqual(self._pixels(result.path), self._pixels(source))
        with Image.open(result.path) as stored:
            self.assertEqual(stored.mode, "RGBA")
            self.assertEqual(stored.getpixel((0, 0)), (0, 0, 0, 0))
            self.assertEqual(stored.getpixel((12, 8)), (180, 40, 20, 255))
        self.assertEqual(source.read_bytes(), original)
        self._assert_no_metadata(result.path)

    def test_damaged_image_is_rejected(self) -> None:
        source = self.sources / "poskozeny.png"
        source.write_bytes(b"\x89PNG\r\n\x1a\n toto neni obrazek")
        with self.assertRaises(WrittenImageError) as rejected:
            normalize_written_image(source, self.output)
        self.assertEqual(str(rejected.exception), IMAGE_LOAD_FAILED)
        self.assertEqual(list(self.output.iterdir()), [self.kept])
        self._assert_kept()

    def test_input_over_limit_is_rejected_before_copy(self) -> None:
        source = self.sources / "velky.jpg"
        with source.open("wb") as handle:
            handle.write(b"\xff\xd8\xff")
            handle.truncate(MAX_INPUT_BYTES + 1)
        with self.assertRaises(WrittenImageError) as rejected:
            normalize_written_image(source, self.output)
        self.assertEqual(str(rejected.exception), IMAGE_TOO_LARGE)
        self.assertEqual(list(self.output.iterdir()), [self.kept])
        self._assert_kept()

    def _assert_kept(self) -> None:
        self.assertEqual(self.kept.read_bytes(), b"stare-bajty-prilohy")
        self.assertEqual(self.kept.stat().st_mtime_ns, self.kept_stamp)

    def _assert_no_metadata(self, path: Path) -> None:
        payload = path.read_bytes()
        self.assertNotIn(_TRAILER, payload)
        self.assertNotIn(_COMMENT, payload)
        self.assertNotIn(_MAKE.encode("ascii"), payload)
        self.assertNotIn(_GPS_MARK.encode("ascii"), payload)
        with Image.open(path) as image:
            exif = image.getexif()
            self.assertFalse(list(exif.keys()))
            self.assertFalse(exif.get_ifd(IFD.GPSInfo))
            self.assertNotIn("icc_profile", image.info)
            self.assertNotIn("comment", image.info)
            self.assertNotIn("exif", image.info)

    def _assert_color(self, path: Path, color: tuple[int, int, int]) -> None:
        with Image.open(path) as image:
            pixels = self._pixel_list(image.convert("RGB"))
        for pixel in pixels:
            for actual, expected in zip(pixel, color, strict=True):
                self.assertLessEqual(abs(int(actual) - expected), 8)

    def _assert_side(self, path: Path, side: str, expected: tuple[int, int, int]) -> None:
        actual = self._side_average(path, side)
        for channel, wanted in zip(actual, expected, strict=True):
            self.assertLessEqual(abs(channel - wanted), 12)

    def _side_average(self, image_or_path, side: str) -> tuple[int, int, int]:
        if isinstance(image_or_path, Path):
            with Image.open(image_or_path) as image:
                return self._side_average(image, side)
        rgb = image_or_path.convert("RGB")
        width, height = rgb.size
        span = max(1, width // 4)
        columns = range(span) if side == "left" else range(width - span, width)
        total = [0, 0, 0]
        count = 0
        for x in columns:
            for y in range(height):
                pixel = rgb.getpixel((x, y))
                for index, channel in enumerate(pixel):
                    total[index] += int(channel)
                count += 1
        return tuple(channel // count for channel in total)

    def _png(self, path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> Path:
        Image.new("RGB", size, color).save(path, "PNG")
        return path

    def _pixels(self, path: Path) -> list[tuple[int, ...]]:
        with Image.open(path) as image:
            return self._pixel_list(image)

    def _pattern(self, size: tuple[int, int], color: tuple[int, int, int]) -> list[tuple[int, ...]]:
        return self._pixel_list(Image.new("RGB", size, color))

    def _pixel_list(self, image: Image.Image) -> list[tuple[int, ...]]:
        return [tuple(pixel) for pixel in image.get_flattened_data()]
