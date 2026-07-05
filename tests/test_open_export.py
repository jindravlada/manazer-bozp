import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from core.export.open_export import (
    _APPIMAGE_ENV_KEYS,
    _cleaned_system_env,
    _strip_appimage_path_entries,
    open_export_file,
)


class OpenExportFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_strip_appimage_path_entries(self) -> None:
        with patch.dict(
            os.environ,
            {"APPDIR": "/tmp/.mount_app/usr"},
            clear=False,
        ):
            cleaned = _strip_appimage_path_entries(
                "/tmp/.mount_app/usr/bin:/usr/bin:/bin"
            )

        self.assertEqual(cleaned, "/usr/bin:/bin")

    def test_cleaned_system_env_removes_appimage_variables(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APPIMAGE": "/tmp/app.AppImage",
                "APPDIR": "/tmp/.mount_app/usr",
                "ARGV0": "/tmp/app.AppImage",
                "LD_LIBRARY_PATH": "/tmp/lib",
                "PYTHONHOME": "/tmp/py",
                "PYTHONPATH": "/tmp/site-packages",
                "PATH": "/tmp/.mount_app/usr/bin:/usr/bin:/bin",
                "HOME": "/home/test",
            },
            clear=False,
        ):
            env = _cleaned_system_env()

        for key in _APPIMAGE_ENV_KEYS:
            self.assertNotIn(key, env)
        self.assertEqual(env["HOME"], "/home/test")
        self.assertNotIn(".mount_", env["PATH"])

    @patch.dict(os.environ, {"APPIMAGE": "/tmp/ManazerBozp.AppImage", "APPDIR": "/tmp/.mount_app/usr"}, clear=False)
    @patch("core.export.open_export._open_with_gio", return_value=True)
    @patch("core.export.open_export._open_with_system_xdg_open")
    @patch("core.export.open_export._open_with_snap_libreoffice")
    @patch("core.export.open_export._open_with_libreoffice")
    def test_appimage_prefers_gio_open(
        self,
        mock_libreoffice,
        mock_snap,
        mock_xdg,
        mock_gio,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")

            result = open_export_file(path)

            self.assertTrue(result)
            mock_gio.assert_called_once()
            mock_xdg.assert_not_called()
            mock_snap.assert_not_called()
            mock_libreoffice.assert_not_called()

    @patch.dict(os.environ, {"APPIMAGE": "/tmp/ManazerBozp.AppImage", "APPDIR": "/tmp/.mount_app/usr"}, clear=False)
    @patch("core.export.open_export._open_with_gio", return_value=False)
    @patch("core.export.open_export._open_with_system_xdg_open", return_value=True)
    @patch("core.export.open_export._open_with_snap_libreoffice")
    def test_appimage_falls_back_to_system_xdg_open(self, mock_snap, mock_xdg, mock_gio) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")

            result = open_export_file(path)

            self.assertTrue(result)
            mock_gio.assert_called_once()
            mock_xdg.assert_called_once()
            mock_snap.assert_not_called()

    @patch.dict(os.environ, {"APPIMAGE": "/tmp/ManazerBozp.AppImage"}, clear=False)
    @patch("core.export.open_export._open_appimage_odt", return_value=False)
    @patch("core.export.open_export.QMessageBox.warning")
    def test_appimage_shows_message_when_all_openers_fail(self, mock_warning, mock_open) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")

            result = open_export_file(path, title="Test export")

            self.assertFalse(result)
            mock_open.assert_called_once_with(path.resolve())
            mock_warning.assert_called_once()
            self.assertIn(str(path.resolve()), mock_warning.call_args.args[2])

    @patch("core.export.open_export.sys.platform", "linux")
    @patch("core.export.open_export._is_appimage", return_value=False)
    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export._open_with_qt_desktop")
    def test_linux_prefers_xdg_open(self, mock_qt, mock_xdg, _mock_appimage) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_xdg.return_value = True

            result = open_export_file(path)

            self.assertTrue(result)
            mock_xdg.assert_called_once_with(path.resolve())
            mock_qt.assert_not_called()

    @patch("core.export.open_export.sys.platform", "linux")
    @patch("core.export.open_export._is_appimage", return_value=False)
    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export._open_with_qt_desktop")
    def test_linux_falls_back_to_qt_when_xdg_missing(self, mock_qt, mock_xdg, _mock_appimage) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_xdg.return_value = False
            mock_qt.return_value = True

            result = open_export_file(path)

            self.assertTrue(result)
            mock_qt.assert_called_once_with(path.resolve())

    @patch("core.export.open_export.sys.platform", "win32")
    @patch("core.export.open_export._is_appimage", return_value=False)
    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export._open_with_qt_desktop")
    def test_windows_prefers_qt_desktop(self, mock_qt, mock_xdg, _mock_appimage) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_qt.return_value = True

            result = open_export_file(path)

            self.assertTrue(result)
            mock_qt.assert_called_once_with(path.resolve())
            mock_xdg.assert_not_called()

    @patch("core.export.open_export.QMessageBox.warning")
    def test_shows_message_when_file_missing(self, mock_warning) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.odt"

            result = open_export_file(path)

            self.assertFalse(result)
            mock_warning.assert_called_once()
            self.assertIn(str(path.resolve()), mock_warning.call_args.args[2])
