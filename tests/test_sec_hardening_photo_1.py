"""SEC-HARDENING-PHOTO-1a: vědomé Otočit fyzicky otočí originál."""

from __future__ import annotations

import importlib
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog

from core.services.photo_optimization import HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "sec-hardening-photo-1a"
_HOME = _TEST_ROOT / "home"

if _TEST_ROOT.exists():
    shutil.rmtree(_TEST_ROOT)
_HOME.mkdir(parents=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_HOME):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from core.ui.photo_picker_dialog import PhotoPickerDialog
    from moduly.audity.sluzby.audit_reference_photo_service import (
        audit_reference_photo_service,
    )


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_marker_png(directory: Path, name: str, size=(40, 20)) -> Path:
    path = directory / name
    img = Image.new("RGB", size, color=(0, 0, 0))
    img.putpixel((0, 0), (255, 0, 0))
    img.save(path, format="PNG")
    return path


class SecHardeningPhoto1aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def setUp(self) -> None:
        self.photos_dir = _TEST_ROOT / "photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        for child in self.photos_dir.iterdir():
            if child.is_file():
                child.unlink()

    def _open_dialog(self, photo: Path) -> PhotoPickerDialog:
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog._list.setCurrentRow(0)
        self.assertEqual(dialog._selected_path, photo.resolve())
        return dialog

    def test_1_rotate_physically_changes_original(self) -> None:
        photo = _make_marker_png(self.photos_dir, "rotate.png")
        before = photo.read_bytes()
        dialog = self._open_dialog(photo)
        dialog._rotate_selected(-90)
        self.assertNotEqual(photo.read_bytes(), before)
        self.assertEqual(dialog.selected_path(), photo.resolve())
        with Image.open(photo) as img:
            self.assertEqual(img.size, (20, 40))
            self.assertEqual(img.getpixel((0, 39)), (255, 0, 0))
        self.assertIn("20", dialog._info_dims.text())
        self.assertIn("40", dialog._info_dims.text())

    def test_2_rotate_then_cancel_keeps_original_rotated(self) -> None:
        photo = _make_marker_png(self.photos_dir, "cancel.png")
        dialog = self._open_dialog(photo)
        dialog._rotate_selected(90)
        with Image.open(photo) as img:
            rotated_size = img.size
            rotated_pixel = img.getpixel((19, 0))
        dialog.reject()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        with Image.open(photo) as img:
            self.assertEqual(img.size, rotated_size)
            self.assertEqual(img.getpixel((19, 0)), rotated_pixel)

    def test_3_rotate_then_confirm_returns_rotated_original(self) -> None:
        photo = _make_marker_png(self.photos_dir, "confirm.png")
        dialog = self._open_dialog(photo)
        dialog._rotate_selected(-90)
        dialog._accept_selection()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        result = dialog.selected_path()
        self.assertEqual(result, photo.resolve())
        with Image.open(result) as img:
            self.assertEqual(img.size, (20, 40))
            self.assertEqual(img.getpixel((0, 39)), (255, 0, 0))

    def test_4_select_without_rotate_leaves_original_untouched(self) -> None:
        photo = _make_marker_png(self.photos_dir, "plain.png")
        before = photo.read_bytes()
        dialog = self._open_dialog(photo)
        dialog._accept_selection()
        self.assertEqual(dialog.selected_path(), photo.resolve())
        self.assertEqual(photo.read_bytes(), before)

    def test_5_repeated_rotate_updates_original_and_preview(self) -> None:
        photo = _make_marker_png(self.photos_dir, "repeat.png")
        dialog = self._open_dialog(photo)
        dialog._rotate_selected(-90)
        with Image.open(photo) as img:
            self.assertEqual(img.size, (20, 40))
        self.assertIn("20", dialog._info_dims.text())
        self.assertIn("40", dialog._info_dims.text())

        dialog._rotate_selected(-90)
        with Image.open(photo) as img:
            self.assertEqual(img.size, (40, 20))
            self.assertEqual(img.getpixel((39, 19)), (255, 0, 0))
        self.assertIn("40", dialog._info_dims.text())
        self.assertIn("20", dialog._info_dims.text())
        self.assertEqual(dialog.selected_path(), photo.resolve())

    def test_saved_photo_stays_under_1mb_after_rotate(self) -> None:
        photo = self.photos_dir / "large.jpg"
        image = Image.new("RGB", (1800, 1400), color=(30, 80, 140))
        image.save(photo, format="JPEG", quality=95)
        dialog = self._open_dialog(photo)
        dialog._rotate_selected(90)
        dialog._accept_selection()
        result = dialog.selected_path()
        self.assertEqual(result, photo.resolve())
        relative = audit_reference_photo_service.save_optimized(
            result,
            process_id="proc",
            criterion_id="crit",
            photo_id="photo1",
        )
        stored = audit_reference_photo_service.absolute_photo_path(relative)
        self.assertTrue(stored.is_file())
        self.assertLessEqual(stored.stat().st_size, HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES)
        self.assertLessEqual(stored.stat().st_size, 1 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
