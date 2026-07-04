import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from core.export.open_export import open_export_file


class OpenExportFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export.QDesktopServices.openUrl")
    def test_uses_resolved_absolute_path(self, mock_open_url, mock_xdg_open) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_open_url.return_value = True

            result = open_export_file(path)

            self.assertTrue(result)
            mock_open_url.assert_called_once()
            url = mock_open_url.call_args.args[0]
            self.assertIsInstance(url, QUrl)
            self.assertEqual(url.toLocalFile(), str(path.resolve()))
            mock_xdg_open.assert_not_called()

    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export.QDesktopServices.openUrl")
    def test_falls_back_to_xdg_open_when_qt_fails(self, mock_open_url, mock_xdg_open) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_open_url.return_value = False
            mock_xdg_open.return_value = True

            result = open_export_file(path)

            self.assertTrue(result)
            mock_xdg_open.assert_called_once_with(path.resolve())

    @patch.dict("os.environ", {"APPIMAGE": "/tmp/ManazerBozp.AppImage"}, clear=False)
    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export.QDesktopServices.openUrl")
    def test_appimage_uses_xdg_open_without_qt(self, mock_open_url, mock_xdg_open) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_xdg_open.return_value = True

            result = open_export_file(path)

            self.assertTrue(result)
            mock_open_url.assert_not_called()
            mock_xdg_open.assert_called_once_with(path.resolve())

    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export.QMessageBox.warning")
    @patch("core.export.open_export.QDesktopServices.openUrl")
    def test_shows_message_when_both_openers_fail(self, mock_open_url, mock_warning, mock_xdg_open) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_open_url.return_value = False
            mock_xdg_open.return_value = False

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
