"""SEC-HARDENING-PHOTO-2: metadata + limit nových interních fotografií 1 MB."""

from __future__ import annotations

import importlib
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageCms
from PIL.ExifTags import IFD
from PIL.TiffImagePlugin import IFDRational
from PySide6.QtWidgets import QApplication

from core.services.photo_optimization import (
    HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES,
    INTERNAL_PHOTO_MAX_BYTES,
    TARGET_MAX_BYTES,
    PhotoOptimizationError,
    optimize_image_bytes,
    optimize_photo_for_storage,
    write_internal_photo_bytes,
)

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "sec-hardening-photo-2"
_HOME = _TEST_ROOT / "home"

if _TEST_ROOT.exists():
    shutil.rmtree(_TEST_ROOT)
_HOME.mkdir(parents=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_HOME):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from core.services.attachment_service import AttachmentService
    from core.services.control_result_photo_service import (
        control_result_photo_service,
    )
    from core.ui.photo_picker_dialog import rotate_photo_file
    from core.widgets.image_viewer_dialog import ImageViewerDialog
    from moduly.audity.sluzby.audit_reference_photo_service import (
        audit_reference_photo_service,
    )
    from moduly.proverky.sluzby.proverky_reference_photo_service import (
        proverky_reference_photo_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_photo_service import (
        hazard_identification_photo_service,
    )


_DTO = "2019:12:31 23:59:58"
_DT = "2020:01:02 03:04:05"


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _gps_tuple():
    return (
        IFDRational(50, 1),
        IFDRational(5, 1),
        IFDRational(0, 1),
    )


def _write_jpeg_with_meta(
    path: Path,
    *,
    size=(320, 240),
    orientation: int = 1,
    icc: bool = True,
) -> Path:
    image = Image.new("RGB", size, (30, 80, 140))
    image.putpixel((0, 0), (255, 0, 0))
    exif = Image.Exif()
    exif[_EXIF_ORIENTATION := 274] = orientation
    exif[306] = _DT
    exif.get_ifd(IFD.Exif)[36867] = _DTO
    exif.get_ifd(IFD.Exif)[36868] = _DTO
    gps = exif.get_ifd(IFD.GPSInfo)
    gps[1] = "N"
    gps[2] = _gps_tuple()
    gps[3] = "E"
    gps[4] = (
        IFDRational(14, 1),
        IFDRational(25, 1),
        IFDRational(0, 1),
    )
    save_kwargs: dict = {"format": "JPEG", "quality": 90, "exif": exif}
    if icc:
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        save_kwargs["icc_profile"] = profile
    image.save(path, **save_kwargs)
    return path


def _write_large_jpeg(path: Path) -> Path:
    image = Image.new("RGB", (3000, 2000))
    pixels = image.load()
    for y in range(0, 2000, 2):
        for x in range(0, 3000, 2):
            pixels[x, y] = ((x * 37) % 256, (y * 53) % 256, ((x + y) * 17) % 256)
    image.save(path, format="JPEG", quality=95)
    return path


def _exif_of(path: Path):
    with Image.open(path) as image:
        return image.getexif()


def _assert_datetime_and_gps(test: unittest.TestCase, path: Path) -> None:
    exif = _exif_of(path)
    test.assertEqual(exif.get(306), _DT)
    test.assertEqual(exif.get_ifd(IFD.Exif).get(36867), _DTO)
    gps = dict(exif.get_ifd(IFD.GPSInfo).items())
    test.assertEqual(gps.get(1), "N")
    test.assertEqual(tuple(float(v) for v in gps.get(2)), (50.0, 5.0, 0.0))
    test.assertEqual(gps.get(3), "E")
    test.assertEqual(tuple(float(v) for v in gps.get(4)), (14.0, 25.0, 0.0))


class SecHardeningPhoto2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def setUp(self) -> None:
        self.work = _TEST_ROOT / "work"
        self.work.mkdir(parents=True, exist_ok=True)
        for child in self.work.iterdir():
            if child.is_file():
                child.unlink()

    def test_a_new_jpeg_keeps_datetime_and_gps(self) -> None:
        source = _write_jpeg_with_meta(self.work / "meta.jpg")
        before = source.read_bytes()
        result = optimize_photo_for_storage(source)
        self.assertLessEqual(len(result.data), TARGET_MAX_BYTES)
        self.assertEqual(result.taken_at.strftime("%Y:%m:%d %H:%M:%S"), _DTO)
        stored = self.work / "stored-a.jpg"
        write_internal_photo_bytes(stored, result.data)
        _assert_datetime_and_gps(self, stored)
        self.assertEqual(_exif_of(stored).get(274), 1)
        with Image.open(stored) as image:
            self.assertTrue(image.info.get("icc_profile"))
        self.assertEqual(source.read_bytes(), before)

    def test_b_rotate_then_store_keeps_orientation_datetime_gps(self) -> None:
        source = _write_jpeg_with_meta(
            self.work / "rotate.jpg",
            size=(80, 40),
            orientation=1,
        )
        rotate_photo_file(source, -90)
        self.assertEqual(_exif_of(source).get(274), 1)
        _assert_datetime_and_gps(self, source)
        stored = self.work / "stored-b.jpg"
        write_internal_photo_bytes(stored, optimize_image_bytes(source))
        self.assertEqual(_exif_of(stored).get(274), 1)
        _assert_datetime_and_gps(self, stored)
        with Image.open(stored) as image:
            self.assertEqual(image.size, (40, 80))

    def test_c_large_new_photo_is_at_most_1mb(self) -> None:
        source = _write_large_jpeg(self.work / "large.jpg")
        self.assertGreater(source.stat().st_size, INTERNAL_PHOTO_MAX_BYTES)
        before = source.read_bytes()
        data = optimize_image_bytes(source)
        self.assertLessEqual(len(data), TARGET_MAX_BYTES)
        self.assertLessEqual(len(data), INTERNAL_PHOTO_MAX_BYTES)
        self.assertEqual(source.read_bytes(), before)

    def test_d_failed_optimize_does_not_copy2_or_write_oversize(self) -> None:
        source = _write_jpeg_with_meta(self.work / "fail.jpg")
        target_dir = self.work / "out"
        target = target_dir / "fail.jpg"
        service = AttachmentService()

        with patch(
            "core.services.attachment_service.optimize_image_bytes",
            side_effect=PhotoOptimizationError("nelze zmenšit"),
        ), patch("core.services.attachment_service.shutil.copy2") as copy2:
            with self.assertRaises(PhotoOptimizationError):
                service._store_source_file(source, target)
            copy2.assert_not_called()
        self.assertFalse(target.exists())
        self.assertFalse(target.with_suffix(".jpg").exists())
        self.assertFalse(target_dir.exists() and any(target_dir.iterdir()))

        with patch(
            "core.services.attachment_service.optimize_image_bytes",
            return_value=b"x" * (INTERNAL_PHOTO_MAX_BYTES + 1),
        ), patch("core.services.attachment_service.shutil.copy2") as copy2:
            with self.assertRaises(PhotoOptimizationError):
                service._store_source_file(source, target)
            copy2.assert_not_called()
        stored = list(target_dir.glob("*")) if target_dir.exists() else []
        self.assertEqual(stored, [])

        with patch(
            "core.services.photo_optimization._encode_jpeg",
            return_value=b"x" * (INTERNAL_PHOTO_MAX_BYTES + 8),
        ):
            with self.assertRaises(PhotoOptimizationError):
                optimize_photo_for_storage(source)
        dest = self.work / "oversize.jpg"
        with self.assertRaises(PhotoOptimizationError):
            write_internal_photo_bytes(dest, b"x" * (INTERNAL_PHOTO_MAX_BYTES + 1))
        self.assertFalse(dest.exists())

    def test_e_existing_oversize_photo_is_not_rewritten(self) -> None:
        historic = _write_large_jpeg(self.work / "historic.jpg")
        self.assertGreater(historic.stat().st_size, INTERNAL_PHOTO_MAX_BYTES)
        before = historic.read_bytes()
        dialog = ImageViewerDialog(historic, title="Fotografie")
        self.addCleanup(dialog.close)
        pixmap = dialog._original_pixmap
        self.assertIsNotNone(pixmap)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(historic.read_bytes(), before)
        self.assertGreater(historic.stat().st_size, INTERNAL_PHOTO_MAX_BYTES)

    def test_f_representative_workflows_store_under_limit_with_metadata(self) -> None:
        source = _write_jpeg_with_meta(self.work / "workflow.jpg", size=(640, 480))
        before = source.read_bytes()

        audit_rel = audit_reference_photo_service.save_optimized(
            source,
            process_id="proc-p2",
            criterion_id="crit-p2",
            photo_id="photo-p2",
        )
        audit_path = audit_reference_photo_service.absolute_photo_path(audit_rel)
        self.assertTrue(audit_path.is_file())
        self.assertLessEqual(audit_path.stat().st_size, TARGET_MAX_BYTES)
        _assert_datetime_and_gps(self, audit_path)
        self.assertEqual(_exif_of(audit_path).get(274), 1)

        proverky_rel = proverky_reference_photo_service.save_optimized(
            source,
            area_id="oblast-p2",
            section_id="sekce-p2",
            photo_id="photo-p2",
        )
        proverky_path = proverky_reference_photo_service.absolute_photo_path(
            proverky_rel
        )
        self.assertTrue(proverky_path.is_file())
        self.assertLessEqual(proverky_path.stat().st_size, TARGET_MAX_BYTES)
        _assert_datetime_and_gps(self, proverky_path)

        control_rel = control_result_photo_service.save_optimized(
            source,
            entity_type="audity",
            entity_id=91,
            area_id="oblast",
            section_id="sekce",
            control_point_id="bod",
        )
        control_path = control_result_photo_service.absolute_photo_path(control_rel)
        self.assertTrue(control_path.is_file())
        self.assertLessEqual(control_path.stat().st_size, TARGET_MAX_BYTES)
        _assert_datetime_and_gps(self, control_path)

        att_target = self.work / "attachments" / "risk.jpg"
        stored, stored_name = AttachmentService()._store_source_file(source, att_target)
        self.assertEqual(Path(stored_name).suffix.lower(), ".jpg")
        self.assertLessEqual(stored.stat().st_size, TARGET_MAX_BYTES)
        _assert_datetime_and_gps(self, stored)

        optimized = hazard_identification_photo_service._optimize(source)
        self.assertLessEqual(len(optimized.data), HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES)
        hazard_path = self.work / "hazard.jpg"
        write_internal_photo_bytes(hazard_path, optimized.data)
        _assert_datetime_and_gps(self, hazard_path)
        self.assertEqual(optimized.taken_at.strftime("%Y:%m:%d %H:%M:%S"), _DTO)

        self.assertEqual(source.read_bytes(), before)

    def test_g_non_photo_attachment_is_copied_byte_for_byte(self) -> None:
        source = self.work / "protokol.odt"
        payload = b"PK\x03\x04-odt-photo-2"
        source.write_bytes(payload)
        target = self.work / "attachments" / "protokol.odt"
        with patch("core.services.attachment_service.shutil.copy2", wraps=shutil.copy2) as copy2:
            stored, stored_name = AttachmentService()._store_source_file(source, target)
            copy2.assert_called_once()
        self.assertEqual(stored_name, "protokol.odt")
        self.assertEqual(stored.read_bytes(), payload)
        self.assertEqual(source.read_bytes(), payload)

        pdf = self.work / "dokument.pdf"
        pdf.write_bytes(b"%PDF-1.4 photo-2")
        pdf_target = self.work / "attachments" / "dokument.pdf"
        stored_pdf, name_pdf = AttachmentService()._store_source_file(pdf, pdf_target)
        self.assertEqual(name_pdf, "dokument.pdf")
        self.assertEqual(stored_pdf.read_bytes(), pdf.read_bytes())

    def test_h_source_stays_byte_for_byte_after_optimize(self) -> None:
        source = _write_jpeg_with_meta(self.work / "origin.jpg")
        before = source.read_bytes()
        optimize_image_bytes(source)
        audit_reference_photo_service.save_optimized(
            source,
            process_id="orig",
            criterion_id="keep",
            photo_id="src",
        )
        AttachmentService()._store_source_file(
            source,
            self.work / "copy-origin.jpg",
        )
        self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
