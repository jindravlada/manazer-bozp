import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from core.export.open_export import open_export_file


class OpenExportFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    @patch("core.export.open_export.sys.platform", "linux")
    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export._open_with_qt_desktop")
    def test_linux_prefers_xdg_open(self, mock_qt, mock_xdg) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_xdg.return_value = True

            result = open_export_file(path)

            self.assertTrue(result)
            mock_xdg.assert_called_once_with(path.resolve())
            mock_qt.assert_not_called()

    @patch("core.export.open_export.sys.platform", "linux")
    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export._open_with_qt_desktop")
    def test_linux_falls_back_to_qt_when_xdg_missing(self, mock_qt, mock_xdg) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_xdg.return_value = False
            mock_qt.return_value = True

            result = open_export_file(path)

            self.assertTrue(result)
            mock_qt.assert_called_once_with(path.resolve())

    @patch("core.export.open_export.sys.platform", "win32")
    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export._open_with_qt_desktop")
    def test_windows_prefers_qt_desktop(self, mock_qt, mock_xdg) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.odt"
            path.write_text("test", encoding="utf-8")
            mock_qt.return_value = True

            result = open_export_file(path)

            self.assertTrue(result)
            mock_qt.assert_called_once_with(path.resolve())
            mock_xdg.assert_not_called()

    @patch("core.export.open_export.sys.platform", "linux")
    @patch("core.export.open_export._open_with_xdg_open")
    @patch("core.export.open_export._open_with_qt_desktop")
    @patch("core.export.open_export.QMessageBox.warning")
    def test_shows_message_when_both_openers_fail(self, mock_warning, mock_qt, mock_xdg) -> None:
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
