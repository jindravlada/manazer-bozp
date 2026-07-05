import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from core.export.open_export import (
    _APPIMAGE_ENV_KEYS,
    _cleaned_system_env,
    open_export_file,
)


class OpenExportFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_cleaned_system_env_removes_appimage_variables(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APPIMAGE": "/tmp/app.AppImage",
                "APPDIR": "/tmp/squashfs-root",
                "ARGV0": "/tmp/app.AppImage",
                "LD_LIBRARY_PATH": "/tmp/lib",
                "PYTHONHOME": "/tmp/py",
                "PYTHONPATH": "/tmp/site-packages",
                "HOME": "/home/test",
            },
            clear=False,
        ):
            env = _cleaned_system_env()

        for key in _APPIMAGE_ENV_KEYS:
            self.assertNotIn(key, env)
        self.assertEqual(env["HOME"], "/home/test")

    @patch.dict(os.environ, {"APPIMAGE": "/tmp/ManazerBozp.AppImage"}, clear=False)
    @patch("core.export.open_export.subprocess.Popen")
    @patch("core.export.open_export._find_executable", return_value="/usr/bin/libreoffice")
    def test_appimage_opens_odt_with_libreoffice_and_clean_env(self, mock_find, mock_popen) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")

            result = open_export_file(path)

            self.assertTrue(result)
            mock_find.assert_called_once()
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            self.assertEqual(args[0], ["/usr/bin/libreoffice", "--writer", str(path.resolve())])
            self.assertFalse(kwargs.get("shell", False))
            env = kwargs["env"]
            for key in _APPIMAGE_ENV_KEYS:
                self.assertNotIn(key, env)

    @patch.dict(os.environ, {"APPIMAGE": "/tmp/ManazerBozp.AppImage"}, clear=False)
    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export._open_with_libreoffice", return_value=False)
    @patch("core.export.open_export.QMessageBox.warning")
    def test_appimage_shows_message_when_libreoffice_missing(
        self,
        mock_warning,
        mock_libreoffice,
        mock_xdg,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")

            result = open_export_file(path, title="Test export")

            self.assertFalse(result)
            mock_libreoffice.assert_called_once_with(path.resolve())
            mock_xdg.assert_not_called()
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

    @patch("core.export.open_export.sys.platform", "linux")
    @patch("core.export.open_export._is_appimage", return_value=False)
    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export._open_with_qt_desktop")
    @patch("core.export.open_export.QMessageBox.warning")
    def test_shows_message_when_both_openers_fail(
        self,
        mock_warning,
        mock_qt,
        mock_xdg,
        _mock_appimage,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_xdg.return_value = False
            mock_qt.return_value = False

            result = open_export_file(path, title="Test export")

            self.assertFalse(result)
            mock_warning.assert_called_once()
            message = mock_warning.call_args.args[2]
            self.assertIn("Export byl vytvořen", message)
            self.assertIn(str(path.resolve()), message)

    @patch("core.export.open_export.QMessageBox.warning")
    def test_shows_message_when_file_missing(self, mock_warning) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.odt"

            result = open_export_file(path)

            self.assertFalse(result)
            mock_warning.assert_called_once()
            self.assertIn(str(path.resolve()), mock_warning.call_args.args[2])
