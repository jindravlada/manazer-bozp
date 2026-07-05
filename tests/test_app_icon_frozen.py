import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication


class AppIconFrozenTests(unittest.TestCase):
    _app: QApplication | None = None

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_app_icon_path_uses_meipass_in_frozen_build(self) -> None:
        resources_dir = Path(__file__).resolve().parents[1] / "core" / "resources"
        fake_meipass = resources_dir.parents[1]

        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "_MEIPASS", str(fake_meipass), create=True):
                from core.resources import app_icon

                path = app_icon.app_icon_path()

        self.assertIsNotNone(path)
        assert path is not None
        self.assertEqual(path.parent.resolve(), resources_dir.resolve())


if __name__ == "__main__":
    unittest.main()
