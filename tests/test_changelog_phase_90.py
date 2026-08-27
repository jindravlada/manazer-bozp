import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPlainTextEdit

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.help.changelog_service import (
        CHANGELOG_FILENAME,
        changelog_exists,
        changelog_path,
        load_changelog_text,
        project_root,
    )
    from core.windows.changelog_dialog import ChangelogDialog
    from core.windows.help_menu import (
        HELP_MENU_TITLE,
        VERSION_HISTORY_ACTION_TITLE,
        show_version_history,
    )


class ChangelogPhase90TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_changelog_file_exists_in_project_root(self) -> None:
        path = project_root() / CHANGELOG_FILENAME
        self.assertTrue(path.is_file(), f"Chybí soubor {path}")

    def test_changelog_contains_release_notes_for_3_4_5(self) -> None:
        content = load_changelog_text()

        self.assertIn("# Verze 3.4.5", content)
        self.assertIn("27. 8. 2026", content)
        self.assertIn("Manažer BOZP 3.4.5", content)

    def test_changelog_contains_release_notes_for_3_4_0(self) -> None:
        content = load_changelog_text()

        self.assertIn("# Verze 3.4.0", content)
        self.assertIn("7. 8. 2026", content)
        self.assertIn("Agenda", content)
        self.assertIn("Šablony událostí", content)
        self.assertIn("Ohláška odborové organizaci", content)
        self.assertIn("podobností", content)

    def test_changelog_contains_release_notes_for_3_1_0(self) -> None:
        content = load_changelog_text()

        self.assertIn("# Verze 3.1.0", content)
        self.assertIn("10. 7. 2026", content)
        self.assertIn("Registr právních požadavků", content)
        self.assertIn("Globální vyhledávání", content)
        self.assertIn("GNU GPL v3", content)

    def test_changelog_service_resolves_existing_path(self) -> None:
        self.assertTrue(changelog_exists())
        self.assertEqual(changelog_path().name, CHANGELOG_FILENAME)

    def test_help_menu_constants_are_prepared(self) -> None:
        self.assertEqual(HELP_MENU_TITLE, "Nápověda")
        self.assertEqual(VERSION_HISTORY_ACTION_TITLE, "Historie verzí")

    def test_version_history_dialog_shows_changelog(self) -> None:
        dialog = ChangelogDialog()
        viewer = dialog.findChild(QPlainTextEdit)
        self.assertIsNotNone(viewer)
        assert viewer is not None
        text = viewer.toPlainText()
        self.assertIn("Verze 3.4.5", text)
        self.assertIn("Verze 3.4.0", text)
        self.assertIn("Verze 3.1.0", text)

    def test_show_version_history_opens_dialog(self) -> None:
        with patch("core.windows.help_menu.ChangelogDialog") as mock_dialog_cls:
            show_version_history()
        mock_dialog_cls.return_value.exec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
