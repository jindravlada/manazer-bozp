import importlib
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.version import (
        APP_AUTHOR,
        APP_COPYRIGHT,
        APP_VERSION,
        app_display_name,
        installer_output_basename,
    )
    from core.windows.about_dialog import AboutDialog
    from core.windows.main_window import MainWindow


class VersionPhase89TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_central_version_is_3_4_0(self) -> None:
        self.assertEqual(APP_VERSION, "3.4.0")
        self.assertEqual(app_display_name(), "Manažer BOZP 3.4.0")

    def test_main_window_title_uses_central_version(self) -> None:
        # Izolace vůči jiným testům, které mohly přepsat SDÍLENÝ sqlite soubor.
        db_path = storage_module.storage_service.database_path
        if db_path.exists():
            db_path.unlink()
        session_module.dispose_database_engine()
        initialize_database()
        window = MainWindow()
        self.assertEqual(window.windowTitle(), "Manažer BOZP 3.4.0")

    def test_about_dialog_shows_central_version(self) -> None:
        dialog = AboutDialog()
        self.assertIn("3.4.0", dialog.windowTitle())
        labels = {label.text() for label in dialog.findChildren(QLabel)}
        self.assertIn(app_display_name(), labels)
        self.assertIn(APP_AUTHOR, labels)
        self.assertIn(APP_COPYRIGHT, labels)

    def test_generate_version_info_uses_central_version(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        content = (project_root / "version_info.txt").read_text(encoding="utf-8")

        self.assertIn("StringStruct('FileVersion', '3.4.0')", content)
        self.assertIn("StringStruct('ProductVersion', '3.4.0')", content)

    def test_generate_installer_iss_uses_central_version(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        content = (project_root / "installer.iss").read_text(encoding="utf-8")

        self.assertIn('#define MyAppVersion "3.4.0"', content)
        self.assertIn(f"OutputBaseFilename={installer_output_basename()}", content)

    def test_official_runtime_files_do_not_hardcode_old_version(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        checked_files = [
            project_root / "core" / "windows" / "main_window.py",
            project_root / "core" / "services" / "backup_service.py",
            project_root / "moduly" / "pravni_pozadavky" / "import_export" / "legal_registry_export_service.py",
            project_root / "main.py",
            project_root / "core" / "version.py",
        ]
        forbidden = re.compile(
            r"Manažer BOZP 3\.(?:0(?:\.0)?|1\.0|2\.0|3\.\d+)|"
            r"APP_VERSION\s*=\s*\"3\.(?:0|1\.0|2\.0|3\.\d+)\""
        )

        for path in checked_files:
            content = path.read_text(encoding="utf-8")
            self.assertIsNone(
                forbidden.search(content),
                msg=f"Soubor {path} stále obsahuje natvrdo zapsanou starou verzi.",
            )


if __name__ == "__main__":
    unittest.main()
