"""UX-PHOTO-1 / UX-PHOTO-2 – testy společného PhotoPickerDialog."""

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
from PySide6.QtWidgets import QApplication, QDialog

_TMP = Path(tempfile.mkdtemp(prefix="ux-photo-1a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from core.ui.photo_picker_dialog import (
        PHOTO_PICKER_SELECT_LABEL,
        THUMB_GRID_SIZE,
        THUMB_ICON_SIZE,
        PhotoPickerDialog,
        fit_image_on_canvas,
        get_last_photo_directory,
        is_supported_photo,
        list_photo_files,
        resolve_initial_directory,
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


if __name__ == "__main__":
    unittest.main()
