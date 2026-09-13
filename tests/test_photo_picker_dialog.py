"""UX-PHOTO-1 / UX-PHOTO-2 / UX-PHOTO-3 – testy společného PhotoPickerDialog."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="ux-photo-1a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from core.ui.photo_picker_dialog import (
        PHOTO_PICKER_ROTATE_UNSUPPORTED,
        PHOTO_PICKER_SELECT_LABEL,
        THUMB_GRID_SIZE,
        THUMB_ICON_SIZE,
        PhotoPickerDialog,
        PhotoRotateError,
        fit_image_on_canvas,
        get_last_photo_directory,
        is_supported_photo,
        list_photo_files,
        resolve_initial_directory,
        rotate_photo_file,
        set_last_photo_directory,
    )


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class PhotoPickerDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def setUp(self) -> None:
        self.photos_dir = _TMP / "photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        for child in self.photos_dir.iterdir():
            if child.is_file():
                child.unlink()
        settings = storage_module.storage_service.config_dir / "ui.ini"
        if settings.exists():
            settings.unlink()

    def _make_jpg(self, name: str, size=(40, 30), color=(10, 80, 160)) -> Path:
        path = self.photos_dir / name
        Image.new("RGB", size, color=color).save(path, format="JPEG")
        return path

    def _make_marker_png(self, name: str, size=(40, 20)) -> Path:
        """PNG s červeným pixelem vlevo nahoře pro kontrolu směru otočení."""
        path = self.photos_dir / name
        img = Image.new("RGB", size, color=(0, 0, 0))
        img.putpixel((0, 0), (255, 0, 0))
        img.save(path, format="PNG")
        return path

    def test_filter_supported_extensions(self) -> None:
        self.assertTrue(is_supported_photo("a.JPG"))
        self.assertTrue(is_supported_photo("a.jpeg"))
        self.assertTrue(is_supported_photo("a.png"))
        self.assertTrue(is_supported_photo("a.webp"))
        self.assertTrue(is_supported_photo("a.heic"))
        self.assertTrue(is_supported_photo("a.heif"))
        self.assertFalse(is_supported_photo("a.pdf"))
        self.assertFalse(is_supported_photo("a.txt"))
        self.assertFalse(is_supported_photo("a.docx"))

    def test_list_ignores_unsupported_files(self) -> None:
        jpg = self._make_jpg("IMG_001.jpg")
        (self.photos_dir / "notes.txt").write_text("x", encoding="utf-8")
        (self.photos_dir / "doc.pdf").write_bytes(b"%PDF")
        files = list_photo_files(self.photos_dir)
        self.assertEqual([p.name for p in files], [jpg.name])

    def test_resolve_initial_and_remember_last_directory(self) -> None:
        other = _TMP / "other_photos"
        other.mkdir()
        resolved = resolve_initial_directory(self.photos_dir)
        self.assertEqual(resolved, self.photos_dir.resolve())

        set_last_photo_directory(self.photos_dir)
        self.assertEqual(get_last_photo_directory(), self.photos_dir.resolve())
        self.assertEqual(
            resolve_initial_directory(None),
            self.photos_dir.resolve(),
        )

        set_last_photo_directory(other)
        self.assertEqual(get_last_photo_directory(), other.resolve())
        # Neexistující cesta se neuloží.
        missing = _TMP / "missing_dir"
        set_last_photo_directory(missing)
        self.assertEqual(get_last_photo_directory(), other.resolve())

    def test_dialog_loads_directory_and_select_disabled_without_selection(self) -> None:
        self._make_jpg("a.jpg")
        self._make_jpg("b.jpg")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.current_directory(), self.photos_dir.resolve())
        self.assertEqual(dialog._list.count(), 2)
        self.assertFalse(dialog._select_btn.isEnabled())
        self.assertEqual(dialog._select_btn.text(), PHOTO_PICKER_SELECT_LABEL)

    def test_change_directory_clears_selection(self) -> None:
        self._make_jpg("one.jpg")
        nested = self.photos_dir / "nested"
        nested.mkdir()
        Image.new("RGB", (20, 20), color=(1, 2, 3)).save(nested / "two.jpg", format="JPEG")

        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog._list.setCurrentRow(0)
        self.assertIsNotNone(dialog.selected_path())

        dialog._load_directory(nested)
        self.assertIsNone(dialog.selected_path())
        self.assertFalse(dialog._select_btn.isEnabled())
        self.assertEqual(dialog._list.count(), 1)

    def test_cancel_returns_none(self) -> None:
        self._make_jpg("x.jpg")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        dialog.reject()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertIsNone(dialog.selected_path())

    def test_select_photo_and_remember_folder(self) -> None:
        photo = self._make_jpg("pick_me.jpg")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog._list.setCurrentRow(0)
        self.assertTrue(dialog._select_btn.isEnabled())
        dialog._accept_selection()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.selected_path(), photo.resolve())
        self.assertEqual(get_last_photo_directory(), self.photos_dir.resolve())

    def test_double_click_accepts(self) -> None:
        photo = self._make_jpg("dbl.jpg")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        item = dialog._list.item(0)
        assert item is not None
        dialog._on_item_double_clicked(item)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.selected_path(), photo.resolve())

    def test_broken_image_does_not_crash_and_cannot_select(self) -> None:
        broken = self.photos_dir / "broken.jpg"
        broken.write_bytes(b"not-an-image")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog._list.count(), 1)
        dialog._list.setCurrentRow(0)
        # Poškozený JPG: dialog běží, výběr není povolen.
        self.assertFalse(dialog._select_btn.isEnabled())
        self.assertIsNone(dialog.selected_path())

    def test_stale_async_thumbnail_ignored_after_directory_change(self) -> None:
        first = self.photos_dir / "first"
        second = self.photos_dir / "second"
        first.mkdir()
        second.mkdir()
        Image.new("RGB", (60, 40), color=(9, 9, 9)).save(first / "a.jpg", format="JPEG")
        Image.new("RGB", (60, 40), color=(9, 9, 9)).save(second / "b.jpg", format="JPEG")

        dialog = PhotoPickerDialog(initial_directory=first)
        self.addCleanup(dialog.close)
        gen_before = dialog._generation
        # Simulace opožděného výsledku ze staré generace.
        dialog._on_thumbnail_finished(
            gen_before,
            str((first / "a.jpg").resolve()),
            None,
            True,
        )
        dialog._load_directory(second)
        stale_gen = gen_before
        dialog._on_thumbnail_finished(
            stale_gen,
            str((first / "a.jpg").resolve()),
            None,
            True,
        )
        # Po změně složky zůstane jen soubor ze second.
        names = [
            Path(str(dialog._list.item(i).data(Qt.ItemDataRole.UserRole))).name
            for i in range(dialog._list.count())
        ]
        self.assertEqual(names, ["b.jpg"])

    def test_dialog_opens_maximized(self) -> None:
        self._make_jpg("max.jpg")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog.show()
        self._app.processEvents()
        self.assertTrue(dialog.isMaximized())

    def test_icon_size_matches_new_setting(self) -> None:
        self._make_jpg("size.jpg")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog._list.iconSize().width(), THUMB_ICON_SIZE)
        self.assertEqual(dialog._list.iconSize().height(), THUMB_ICON_SIZE)
        self.assertEqual(dialog._list.gridSize().width(), THUMB_GRID_SIZE[0])
        self.assertEqual(dialog._list.gridSize().height(), THUMB_GRID_SIZE[1])

    def test_filename_is_shown_above_metadata(self) -> None:
        photo = self._make_jpg("IMG_20260716_123702.jpg")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog._list.setCurrentRow(0)
        self.assertEqual(dialog._info_name.text(), photo.name)
        self.assertTrue(dialog._info_name.font().bold())

        right_layout = dialog._info_name.parentWidget().layout()
        name_idx = right_layout.indexOf(dialog._info_name)
        dims_idx = right_layout.indexOf(dialog._info_dims)
        preview_idx = right_layout.indexOf(dialog._preview)
        self.assertLess(name_idx, dims_idx)
        self.assertLess(dims_idx, preview_idx)

    def test_focus_is_on_photo_list_after_open(self) -> None:
        self._make_jpg("focus.jpg")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog.show()
        self._app.processEvents()
        self.assertIs(dialog.focusWidget(), dialog._list)

    def test_selection_cleared_after_directory_change(self) -> None:
        self._make_jpg("keep.jpg")
        nested = self.photos_dir / "subdir"
        nested.mkdir()
        Image.new("RGB", (24, 24), color=(4, 5, 6)).save(
            nested / "other.jpg", format="JPEG"
        )
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog._list.setCurrentRow(0)
        self.assertIsNotNone(dialog.selected_path())
        dialog._load_directory(nested)
        self.assertIsNone(dialog.selected_path())
        self.assertFalse(dialog._select_btn.isEnabled())
        self.assertEqual(dialog._info_name.text(), "—")

    def test_thumbnail_canvas_keeps_aspect_ratio(self) -> None:
        wide = QImage(320, 80, QImage.Format.Format_RGB32)
        wide.fill(Qt.GlobalColor.blue)
        canvas = fit_image_on_canvas(wide, THUMB_ICON_SIZE)
        self.assertEqual(canvas.width(), THUMB_ICON_SIZE)
        self.assertEqual(canvas.height(), THUMB_ICON_SIZE)
        # Okraje plátna zůstávají průhledné (obrázek je vystředěn).
        corner = canvas.pixelColor(0, 0)
        self.assertEqual(corner.alpha(), 0)

    # --- UX-PHOTO-3: otočení ---

    def test_rotate_left(self) -> None:
        photo = self._make_marker_png("left.png", size=(40, 20))
        before = photo.read_bytes()
        dest = self.photos_dir / "left-rotated.png"
        rotate_photo_file(photo, -90, destination=dest)
        self.assertEqual(photo.read_bytes(), before)
        with Image.open(dest) as img:
            self.assertEqual(img.size, (20, 40))
            # Červený pixel z TL → po CCW dole vlevo.
            self.assertEqual(img.getpixel((0, 39)), (255, 0, 0))

    def test_rotate_right(self) -> None:
        photo = self._make_marker_png("right.png", size=(40, 20))
        before = photo.read_bytes()
        dest = self.photos_dir / "right-rotated.png"
        rotate_photo_file(photo, 90, destination=dest)
        self.assertEqual(photo.read_bytes(), before)
        with Image.open(dest) as img:
            self.assertEqual(img.size, (20, 40))
            # Červený pixel z TL → po CW vpravo nahoře.
            self.assertEqual(img.getpixel((19, 0)), (255, 0, 0))

    def test_rotate_keeps_original_filename_and_location(self) -> None:
        photo = self._make_jpg("keep_name.jpg", size=(30, 20))
        original_name = photo.name
        original_parent = photo.parent.resolve()
        before = photo.read_bytes()
        dest = self.photos_dir / "keep_name-working.jpg"
        result = rotate_photo_file(photo, 90, destination=dest)
        self.assertEqual(photo.name, original_name)
        self.assertEqual(photo.parent.resolve(), original_parent)
        self.assertTrue(photo.exists())
        self.assertEqual(photo.read_bytes(), before)
        self.assertEqual(result, dest.resolve())
        self.assertNotEqual(photo.resolve(), result)

    def test_rotate_fixes_exif_orientation(self) -> None:
        photo = self.photos_dir / "orient.jpg"
        img = Image.new("RGB", (60, 30), color=(12, 34, 56))
        exif = img.getexif()
        exif[274] = 6  # rotate 90 CW via tag
        img.save(photo, format="JPEG", quality=95, exif=exif)
        original_exif = Image.open(photo).getexif().get(274)
        dest = self.photos_dir / "orient-working.jpg"

        rotate_photo_file(photo, -90, destination=dest)
        with Image.open(photo) as original:
            self.assertEqual(original.getexif().get(274), original_exif)
        with Image.open(dest) as out:
            orientation = out.getexif().get(274)
            self.assertIn(orientation, (None, 1))

    def test_rotate_refreshes_thumbnail_and_preview_keeps_selection(self) -> None:
        photo = self._make_jpg("refresh.jpg", size=(80, 40))
        before = photo.read_bytes()
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog._list.setCurrentRow(0)
        item = dialog._list.currentItem()
        assert item is not None
        self.assertFalse(dialog._preview.pixmap() is None or dialog._preview.pixmap().isNull())

        dialog._rotate_selected(-90)

        self.assertEqual(dialog._list.currentRow(), 0)
        self.assertEqual(photo.read_bytes(), before)
        self.assertNotEqual(dialog.selected_path(), photo.resolve())
        self.assertTrue(dialog.selected_path().is_file())
        item_after = dialog._list.currentItem()
        assert item_after is not None
        self.assertFalse(item_after.icon().isNull())
        self.assertFalse(dialog._preview.pixmap() is None or dialog._preview.pixmap().isNull())
        # Rozměry po otočení: 40×80
        self.assertIn("40", dialog._info_dims.text())
        self.assertIn("80", dialog._info_dims.text())

    def test_rotate_write_error_keeps_file_and_continues(self) -> None:
        photo = self._make_jpg("readonly.jpg", size=(20, 10))
        before = photo.read_bytes()
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog._list.setCurrentRow(0)

        with patch(
            "core.ui.photo_picker_dialog.rotate_photo_file",
            side_effect=PhotoRotateError("Soubor se nepodařilo přepsat"),
        ), patch(
            "core.ui.photo_picker_dialog.QMessageBox.warning"
        ) as warn:
            dialog._rotate_selected(90)

        warn.assert_called_once()
        self.assertEqual(photo.read_bytes(), before)
        self.assertEqual(dialog.selected_path(), photo.resolve())
        self.assertEqual(dialog.result(), 0)  # dialog stále otevřený

    def test_rotate_does_not_ask_to_overwrite_original(self) -> None:
        photo = self._make_jpg("ask.jpg", size=(24, 16))
        before = photo.read_bytes()
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog._list.setCurrentRow(0)
        with patch("core.ui.photo_picker_dialog.QMessageBox") as box_cls:
            dialog._rotate_selected(-90)
            box_cls.assert_not_called()
        self.assertEqual(photo.read_bytes(), before)
        self.assertNotEqual(dialog.selected_path(), photo.resolve())

    def test_rotate_buttons_disabled_for_heic(self) -> None:
        heic = self.photos_dir / "phone.heic"
        heic.write_bytes(b"heic-placeholder")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        dialog._list.setCurrentRow(0)
        self.assertFalse(dialog._rotate_left_btn.isEnabled())
        self.assertFalse(dialog._rotate_right_btn.isEnabled())
        self.assertEqual(dialog._rotate_hint.text(), PHOTO_PICKER_ROTATE_UNSUPPORTED)

    def test_rotate_buttons_above_preview(self) -> None:
        self._make_jpg("layout.jpg")
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        right_layout = dialog._preview.parentWidget().layout()
        left_idx = right_layout.indexOf(dialog._rotate_left_btn)
        preview_idx = right_layout.indexOf(dialog._preview)
        rotate_row_idx = None
        for i in range(right_layout.count()):
            item = right_layout.itemAt(i)
            if item is not None and item.layout() is not None:
                layout = item.layout()
                if layout.indexOf(dialog._rotate_left_btn) >= 0:
                    rotate_row_idx = i
                    break
        self.assertIsNotNone(rotate_row_idx)
        self.assertLess(rotate_row_idx, preview_idx)
        self.assertEqual(left_idx, -1)  # tlačítko není přímo v right_layout


if __name__ == "__main__":
    unittest.main()
