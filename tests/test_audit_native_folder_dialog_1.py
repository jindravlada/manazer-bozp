"""AUDIT-NATIVE-FOLDER-DIALOG-1 – nativní výběr složky v AppImage."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QPushButton

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-native-folder-1-"))
_REPO = Path(__file__).resolve().parents[1]

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from core.i18n.qt_translator import install_qt_translators, reset_qt_translators
    from core.packaging.qt_platform_plugins import (
        PLUGIN_DEST,
        PORTAL_PLUGIN,
        pyinstaller_binaries,
        pyinstaller_binary_specs,
    )
    from core.ui.native_folder_dialog import (
        PHOTO_FOLDER_DIALOG_TITLE,
        PORTAL_PLATFORM_THEME,
        choose_existing_directory,
        configure_native_folder_dialogs,
        native_folder_dialog_options,
        prefers_native_folder_dialog,
    )
    from core.ui.photo_picker_dialog import PhotoPickerDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class NativeFolderDialogHelperTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def test_default_options_prefer_native_dialog(self) -> None:
        options = native_folder_dialog_options()
        self.assertTrue(prefers_native_folder_dialog(options))
        self.assertTrue(bool(options & QFileDialog.Option.ShowDirsOnly))
        self.assertFalse(bool(options & QFileDialog.Option.DontUseNativeDialog))

    def test_choose_existing_directory_keeps_czech_title_and_start_dir(self) -> None:
        start = str(_TMP / "start-folder")
        chosen = str(_TMP / "chosen-folder")
        with patch.object(
            QFileDialog, "getExistingDirectory", return_value=chosen
        ) as mocked:
            result = choose_existing_directory(
                None, PHOTO_FOLDER_DIALOG_TITLE, start
            )
        self.assertEqual(result, chosen)
        mocked.assert_called_once()
        args = mocked.call_args[0]
        self.assertEqual(args[1], "Vybrat složku s fotografiemi")
        self.assertEqual(args[2], start)
        self.assertTrue(prefers_native_folder_dialog(args[3]))

    def test_cancel_returns_empty_string(self) -> None:
        with patch.object(QFileDialog, "getExistingDirectory", return_value=""):
            result = choose_existing_directory(None, PHOTO_FOLDER_DIALOG_TITLE, "/x")
        self.assertEqual(result, "")

    def test_native_failure_uses_qt_fallback(self) -> None:
        fallback = str(_TMP / "qt-fallback")
        with patch.object(
            QFileDialog,
            "getExistingDirectory",
            side_effect=[RuntimeError("portal down"), fallback],
        ) as mocked:
            with self.assertLogs("core.ui.native_folder_dialog", level="WARNING"):
                result = choose_existing_directory(
                    None, PHOTO_FOLDER_DIALOG_TITLE, "/start"
                )
        self.assertEqual(result, fallback)
        self.assertEqual(mocked.call_count, 2)
        native_options = mocked.call_args_list[0][0][3]
        fallback_options = mocked.call_args_list[1][0][3]
        self.assertTrue(prefers_native_folder_dialog(native_options))
        self.assertFalse(prefers_native_folder_dialog(fallback_options))
        self.assertEqual(mocked.call_args_list[1][0][1], PHOTO_FOLDER_DIALOG_TITLE)

    def test_diagnostics_do_not_log_user_paths(self) -> None:
        secret = str(_TMP / "tajna-fotografie.jpg")
        with patch.object(QFileDialog, "getExistingDirectory", return_value=""):
            with self.assertLogs("core.ui.native_folder_dialog", level="INFO") as captured:
                choose_existing_directory(None, PHOTO_FOLDER_DIALOG_TITLE, secret)
        joined = "\n".join(captured.output)
        self.assertIn("folder-dialog", joined)
        self.assertIn("native_preferred=True", joined)
        self.assertNotIn("tajna-fotografie", joined)
        self.assertNotIn(secret, joined)


class NativeFolderDialogConfigTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._theme = os.environ.pop("QT_QPA_PLATFORMTHEME", None)
        self._platform = os.environ.get("QT_QPA_PLATFORM")

    def tearDown(self) -> None:
        if self._theme is None:
            os.environ.pop("QT_QPA_PLATFORMTHEME", None)
        else:
            os.environ["QT_QPA_PLATFORMTHEME"] = self._theme
        if self._platform is None:
            os.environ.pop("QT_QPA_PLATFORM", None)
        else:
            os.environ["QT_QPA_PLATFORM"] = self._platform

    def test_source_run_does_not_force_portal_theme(self) -> None:
        with (
            patch("core.ui.native_folder_dialog.is_frozen_app", return_value=False),
            patch("core.ui.native_folder_dialog._qpa_platform", return_value="wayland"),
            patch(
                "core.ui.native_folder_dialog.xdg_desktop_portal_available",
                return_value=True,
            ),
        ):
            configure_native_folder_dialogs()
        self.assertNotIn("QT_QPA_PLATFORMTHEME", os.environ)

    def test_frozen_with_portal_sets_xdgdesktopportal(self) -> None:
        with (
            patch("core.ui.native_folder_dialog.is_frozen_app", return_value=True),
            patch("core.ui.native_folder_dialog._qpa_platform", return_value="wayland"),
            patch(
                "core.ui.native_folder_dialog.xdg_desktop_portal_available",
                return_value=True,
            ),
        ):
            configure_native_folder_dialogs()
        self.assertEqual(os.environ.get("QT_QPA_PLATFORMTHEME"), PORTAL_PLATFORM_THEME)
        self.assertEqual(os.environ.get("QT_QPA_PLATFORM"), self._platform)

    def test_frozen_without_portal_keeps_qt_fallback(self) -> None:
        with (
            patch("core.ui.native_folder_dialog.is_frozen_app", return_value=True),
            patch("core.ui.native_folder_dialog._qpa_platform", return_value="xcb"),
            patch(
                "core.ui.native_folder_dialog.xdg_desktop_portal_available",
                return_value=False,
            ),
        ):
            configure_native_folder_dialogs()
        self.assertNotIn("QT_QPA_PLATFORMTHEME", os.environ)

    def test_does_not_override_existing_platformtheme(self) -> None:
        os.environ["QT_QPA_PLATFORMTHEME"] = "gtk3"
        with (
            patch("core.ui.native_folder_dialog.is_frozen_app", return_value=True),
            patch("core.ui.native_folder_dialog._qpa_platform", return_value="wayland"),
            patch(
                "core.ui.native_folder_dialog.xdg_desktop_portal_available",
                return_value=True,
            ),
        ):
            configure_native_folder_dialogs()
        self.assertEqual(os.environ.get("QT_QPA_PLATFORMTHEME"), "gtk3")

    def test_headless_platform_does_not_set_theme(self) -> None:
        with (
            patch("core.ui.native_folder_dialog.is_frozen_app", return_value=True),
            patch("core.ui.native_folder_dialog._qpa_platform", return_value="offscreen"),
            patch(
                "core.ui.native_folder_dialog.xdg_desktop_portal_available",
                return_value=True,
            ),
        ):
            configure_native_folder_dialogs()
        self.assertNotIn("QT_QPA_PLATFORMTHEME", os.environ)

    def test_configure_never_assigns_qpa_platform(self) -> None:
        source = (_REPO / "core/ui/native_folder_dialog.py").read_text(encoding="utf-8")
        self.assertNotIn('os.environ["QT_QPA_PLATFORM"]', source)
        self.assertNotIn("os.environ['QT_QPA_PLATFORM']", source)


class PhotoFolderBrowseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def setUp(self) -> None:
        self.photos_dir = _TMP / "photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)

    def test_confirm_loads_selected_folder(self) -> None:
        other = _TMP / "other-photos"
        other.mkdir(exist_ok=True)
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        start = dialog.current_directory()
        with patch(
            "core.ui.photo_picker_dialog.choose_existing_directory",
            return_value=str(other),
        ) as mocked:
            dialog._browse_folder()
        mocked.assert_called_once_with(dialog, PHOTO_FOLDER_DIALOG_TITLE, str(start))
        self.assertEqual(dialog.current_directory(), other.resolve())

    def test_cancel_does_not_change_directory(self) -> None:
        dialog = PhotoPickerDialog(initial_directory=self.photos_dir)
        self.addCleanup(dialog.close)
        before = dialog.current_directory()
        with patch(
            "core.ui.photo_picker_dialog.choose_existing_directory",
            return_value="",
        ):
            dialog._browse_folder()
        self.assertEqual(dialog.current_directory(), before)

    def test_photo_picker_does_not_force_non_native_dialog(self) -> None:
        source = (_REPO / "core/ui/photo_picker_dialog.py").read_text(encoding="utf-8")
        self.assertIn("choose_existing_directory", source)
        self.assertNotIn("DontUseNativeDialog", source)
        self.assertNotIn("getExistingDirectory", source)


class QtFallbackCzechTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def tearDown(self) -> None:
        reset_qt_translators(self._app)

    def test_qt_fallback_dialog_still_has_czech_labels(self) -> None:
        install_qt_translators(self._app, force=True)
        dialog = QFileDialog()
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setWindowTitle(PHOTO_FOLDER_DIALOG_TITLE)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(dialog.windowTitle(), "Vybrat složku s fotografiemi")
        labels = [widget.text() for widget in dialog.findChildren(QLabel)]
        buttons = [widget.text() for widget in dialog.findChildren(QPushButton)]
        self.assertTrue(any("Hledat v:" in text for text in labels))
        self.assertTrue(any(text.replace("&", "") == "Zrušit" for text in buttons))
        self.assertEqual(
            QCoreApplication.translate("QFileDialog", "Look in:"),
            "Hledat v:",
        )


class BuildManifestPluginTestCase(unittest.TestCase):
    def test_packaging_helper_collects_portal_plugin_with_relative_dest(self) -> None:
        binaries = pyinstaller_binaries()
        self.assertTrue(binaries)
        portal = [item for item in binaries if item[0].endswith(PORTAL_PLUGIN)]
        self.assertEqual(len(portal), 1)
        src, dest = portal[0]
        self.assertTrue(Path(src).is_file())
        self.assertEqual(dest, PLUGIN_DEST)
        self.assertFalse(dest.startswith("/"))
        specs = pyinstaller_binary_specs()
        self.assertTrue(any(PORTAL_PLUGIN in spec and PLUGIN_DEST in spec for spec in specs))

    def test_build_scripts_and_spec_include_portal_plugin(self) -> None:
        release = (_REPO / "build_release.sh").read_text(encoding="utf-8")
        old = (_REPO / "build_old_release.sh").read_text(encoding="utf-8")
        spec = (_REPO / "ManazerBOZP.spec").read_text(encoding="utf-8")
        main_src = (_REPO / "main.py").read_text(encoding="utf-8")
        for content in (release, old):
            self.assertIn("libqxdgdesktopportal.so", content)
            self.assertIn("qt_platform_plugins", content)
        self.assertIn("pyinstaller_binary_specs", release)
        self.assertIn("pyinstaller_binary_specs", old)
        self.assertIn("from core.packaging.qt_platform_plugins import pyinstaller_binaries", spec)
        self.assertIn("pyinstaller_binaries()", spec)
        self.assertIn("PORTAL_PLUGIN = \"libqxdgdesktopportal.so\"", (_REPO / "core/packaging/qt_platform_plugins.py").read_text(encoding="utf-8"))
        self.assertIn("configure_native_folder_dialogs", main_src)
        self.assertNotIn("QT_QPA_PLATFORMTHEME=gtk2", release)
        self.assertNotIn("QT_QPA_PLATFORMTHEME=gtk2", old)

    def test_simulated_meipass_does_not_break_plugin_lookup(self) -> None:
        fake = Path(tempfile.mkdtemp(prefix="native-folder-meipass-")) / "meipass"
        fake.mkdir(parents=True)
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "_MEIPASS", str(fake), create=True):
                binaries = pyinstaller_binaries()
        self.assertTrue(any(item[0].endswith(PORTAL_PLUGIN) for item in binaries))


if __name__ == "__main__":
    unittest.main()
