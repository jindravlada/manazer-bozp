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

    def test_central_version_is_3_4_5(self) -> None:
        self.assertEqual(APP_VERSION, "3.4.5")
        self.assertEqual(app_display_name(), "Manažer BOZP 3.4.5")

    def test_main_window_title_uses_central_version(self) -> None:
        # Izolace vůči jiným testům, které mohly přepsat SDÍLENÝ sqlite soubor.
        db_path = storage_module.storage_service.database_path
        if db_path.exists():
            db_path.unlink()
        session_module.dispose_database_engine()
        initialize_database()
        window = MainWindow()
        self.assertEqual(window.windowTitle(), "Manažer BOZP 3.4.5")
        self.assertEqual(window.windowTitle(), app_display_name())

    def test_about_dialog_shows_central_version(self) -> None:
        dialog = AboutDialog()
        self.assertIn("3.4.5", dialog.windowTitle())
        labels = {label.text() for label in dialog.findChildren(QLabel)}
        self.assertIn(app_display_name(), labels)
        self.assertIn(APP_AUTHOR, labels)
        self.assertIn(APP_COPYRIGHT, labels)

    def test_packaging_metadata_matches_canonical_version(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        major, minor, patch = APP_VERSION.split(".")
        version_tuple = f"({major}, {minor}, {patch}, 0)"

        version_info = (project_root / "version_info.txt").read_text(encoding="utf-8")
        self.assertIn(f"filevers={version_tuple}", version_info)
        self.assertIn(f"prodvers={version_tuple}", version_info)
        self.assertIn(f"StringStruct('FileVersion', '{APP_VERSION}')", version_info)
        self.assertIn(f"StringStruct('ProductVersion', '{APP_VERSION}')", version_info)
        self.assertNotIn("3.4.0", version_info)

        installer = (project_root / "installer.iss").read_text(encoding="utf-8")
        self.assertIn(f'#define MyAppVersion "{APP_VERSION}"', installer)
        self.assertIn(f"OutputBaseFilename={installer_output_basename()}", installer)
        self.assertEqual(installer_output_basename(), "Manazer_BOZP_3_4_5_Setup")
        self.assertNotIn("3.4.0", installer)

        readme = (project_root / "README.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith(f"# {app_display_name()}"))

        for script_name in ("build_release.sh", "build_old_release.sh"):
            script = (project_root / script_name).read_text(encoding="utf-8")
            self.assertIn("from core.version import app_display_name", script)
            self.assertNotIn("3.4.0", script)
            self.assertNotIn("3.2.0", script)

    def test_generate_version_info_uses_central_version(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        content = (project_root / "version_info.txt").read_text(encoding="utf-8")

        self.assertIn(f"StringStruct('FileVersion', '{APP_VERSION}')", content)
        self.assertIn(f"StringStruct('ProductVersion', '{APP_VERSION}')", content)

    def test_generate_installer_iss_uses_central_version(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        content = (project_root / "installer.iss").read_text(encoding="utf-8")

        self.assertIn(f'#define MyAppVersion "{APP_VERSION}"', content)
        self.assertIn(f"OutputBaseFilename={installer_output_basename()}", content)

    def test_official_runtime_files_do_not_hardcode_old_version(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        checked_files = [
            project_root / "core" / "windows" / "main_window.py",
            project_root / "core" / "backup" / "package_create.py",
            project_root / "moduly" / "pravni_pozadavky" / "import_export" / "legal_registry_export_service.py",
            project_root / "main.py",
            project_root / "core" / "version.py",
        ]
        forbidden = re.compile(
            r"Manažer BOZP 3\.(?:0(?:\.0)?|1\.0|2\.0|3\.\d+|4\.0)|"
            r"APP_VERSION\s*=\s*\"3\.(?:0|1\.0|2\.0|3\.\d+|4\.0)\""
        )

        for path in checked_files:
            content = path.read_text(encoding="utf-8")
            self.assertIsNone(
                forbidden.search(content),
                msg=f"Soubor {path} stále obsahuje natvrdo zapsanou starou verzi.",
            )


if __name__ == "__main__":
    unittest.main()
