import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication


class AppIconTests(unittest.TestCase):
    _app: QApplication | None = None

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_bundled_icon_file_exists(self) -> None:
        resources_dir = Path(__file__).resolve().parents[1] / "core" / "resources"
        icon_paths = [resources_dir / name for name in ("manager_bozp.png", "manager_bozp.ico")]
        self.assertTrue(
            any(path.is_file() for path in icon_paths),
            f"Missing bundled icon in: {resources_dir}",
        )

    def test_load_app_icon_is_valid(self) -> None:
        from core.resources.app_icon import app_icon_path, load_app_icon, load_app_pixmap

        path = app_icon_path()
        self.assertIsNotNone(path)
        assert path is not None
        self.assertIn(path.name, ("manager_bozp.png", "manager_bozp.ico"))
        self.assertTrue(path.parent.name == "resources")

        icon = load_app_icon()
        self.assertFalse(icon.isNull())
        self.assertGreater(len(icon.availableSizes()), 0)

        pixmap = load_app_pixmap(40)
        self.assertFalse(pixmap.isNull())
        self.assertGreater(pixmap.width(), 0)
        self.assertGreater(pixmap.height(), 0)


if __name__ == "__main__":
    unittest.main()
