import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from core.export.open_export import _APPIMAGE_ENV_KEYS
from core.services.file_location_service import (
    _build_linux_file_commands,
    _linux_external_env,
    _open_in_file_manager,
    open_path_in_file_manager,
)


class FileLocationServicePhase91cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.existing_file = self.root / "backup.zip"
        self.existing_file.write_text("demo", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_empty_path_does_not_open_or_warn(self) -> None:
        with patch("core.services.file_location_service._open_in_file_manager") as mock_open:
            with patch("core.services.file_location_service.QMessageBox.warning") as mock_warning:
                result = open_path_in_file_manager("")
                result_none = open_path_in_file_manager(None)  # type: ignore[arg-type]
        self.assertFalse(result)
        self.assertFalse(result_none)
        mock_open.assert_not_called()
        mock_warning.assert_not_called()

    def test_missing_path_shows_not_found_message(self) -> None:
        missing = self.root / "no-such-dir" / "missing.zip"
        with patch("core.services.file_location_service.QMessageBox.warning") as mock_warning:
            with patch("core.services.file_location_service.QMessageBox.question") as mock_question:
                opened = open_path_in_file_manager(missing)
        self.assertFalse(opened)
        mock_warning.assert_called_once()
        mock_question.assert_not_called()
        self.assertIn("Soubor nebyl nalezen", mock_warning.call_args[0][2])
        self.assertIn(str(missing.resolve()), mock_warning.call_args[0][2])

    def test_missing_file_can_open_parent_directory(self) -> None:
        nested = self.root / "nested"
        nested.mkdir()
        missing = nested / "missing.zip"
        with patch("core.services.file_location_service._open_in_file_manager", return_value=(True, ["gio open"], "")) as mock_open:
            with patch("core.services.file_location_service.QMessageBox.question", return_value=QMessageBox.Yes):
                opened = open_path_in_file_manager(missing)
        self.assertTrue(opened)
        mock_open.assert_called_once_with(nested)

    @patch("core.services.file_location_service.sys.platform", "linux")
    @patch("core.services.file_location_service._system_binary")
    @patch("core.services.file_location_service._run_detached")
    def test_linux_existing_file_opens_parent_directory(
        self,
        mock_run,
        mock_system_binary,
    ) -> None:
        def binary(name: str) -> str | None:
            return {
                "gio": "/usr/bin/gio",
                "xdg-open": "/usr/bin/xdg-open",
            }.get(name)

        mock_system_binary.side_effect = binary
        mock_run.side_effect = lambda command, env=None: command[0] == "/usr/bin/gio"

        opened, attempts, error = _open_in_file_manager(self.existing_file)

        self.assertTrue(opened)
        self.assertEqual(error, "")
        self.assertTrue(any("gio open" in item for item in attempts))
        self.assertTrue(any(str(self.existing_file.parent) in item for item in attempts))
        self.assertIsNotNone(mock_run.call_args.kwargs.get("env"))

    @patch("core.services.file_location_service.sys.platform", "linux")
    @patch("core.services.file_location_service._system_binary")
    @patch("core.services.file_location_service._run_detached")
    def test_linux_falls_back_from_gio_to_xdg_open(
        self,
        mock_run,
        mock_system_binary,
    ) -> None:
        def binary(name: str) -> str | None:
            return {
                "gio": "/usr/bin/gio",
                "xdg-open": "/usr/bin/xdg-open",
            }.get(name)

        mock_system_binary.side_effect = binary

        def run_side_effect(command, env=None):
            return command[0] == "/usr/bin/xdg-open"

        mock_run.side_effect = run_side_effect

        opened, attempts, error = _open_in_file_manager(self.existing_file)

        self.assertTrue(opened)
        self.assertEqual(error, "")
        self.assertIn("/usr/bin/gio open", attempts[0])
        self.assertIn("/usr/bin/xdg-open", attempts[-1])

    @patch("core.services.file_location_service.sys.platform", "win32")
    @patch("core.services.file_location_service._run_detached", return_value=True)
    def test_windows_uses_explorer_select(self, mock_run) -> None:
        opened, attempts, _error = _open_in_file_manager(self.existing_file)
        self.assertTrue(opened)
        mock_run.assert_called_once()
        command = mock_run.call_args.args[0]
        self.assertEqual(command[0], "explorer.exe")
        self.assertEqual(command[1], "/select,")
        self.assertEqual(command[2], str(self.existing_file.resolve()))

    @patch.dict(
        os.environ,
        {
            "APPIMAGE": "/tmp/ManazerBOZP.AppImage",
            "APPDIR": "/tmp/.mount_app/usr",
            "LD_LIBRARY_PATH": "/tmp/.mount_app/usr/lib",
            "PYTHONHOME": "/tmp/.mount_app/usr",
            "PYTHONPATH": "/tmp/.mount_app/usr/lib",
        },
        clear=False,
    )
    def test_appimage_environment_is_cleaned_for_external_process(self) -> None:
        env = _linux_external_env()
        for key in _APPIMAGE_ENV_KEYS:
            self.assertNotIn(key, env)

    @patch("core.services.file_location_service._open_in_file_manager", return_value=(False, [], "spawn failed"))
    def test_subprocess_failure_shows_generic_message_without_crash(self, _mock_open) -> None:
        with patch("core.services.file_location_service.QMessageBox.warning") as mock_warning:
            opened = open_path_in_file_manager(self.existing_file)
        self.assertFalse(opened)
        mock_warning.assert_called_once()
        self.assertEqual(mock_warning.call_args[0][2], "Umístění se nepodařilo otevřít.")

    def test_linux_file_commands_prefer_directory_open_first(self) -> None:
        with patch("core.services.file_location_service._system_binary") as mock_system_binary:
            mock_system_binary.side_effect = lambda name: f"/usr/bin/{name}"
            commands = _build_linux_file_commands(self.existing_file)
        self.assertGreaterEqual(len(commands), 2)
        self.assertEqual(commands[0], ["/usr/bin/gio", "open", str(self.existing_file.parent)])
        self.assertEqual(commands[1], ["/usr/bin/gio", "open", str(self.existing_file.resolve())])


if __name__ == "__main__":
    unittest.main()
