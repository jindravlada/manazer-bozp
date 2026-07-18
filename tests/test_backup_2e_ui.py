"""BACKUP-2e: starý ZIP formát není v běžném UI zálohování."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QGroupBox, QLabel

_TMP = Path(tempfile.mkdtemp(prefix="mbbackup-2e-ui-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.sprava_dat.sluzby.full_backup_workflow_service import (
        full_backup_workflow_service,
    )
    from moduly.sprava_dat.ui.backup_tab import BackupTab
    from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage
    from moduly.sprava_dat.ui.tab_constants import TAB_BACKUP


class Backup2eUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_tab_shows_only_mbbackup_card(self) -> None:
        tab = BackupTab()
        titles = [group.title() for group in tab.findChildren(QGroupBox)]
        self.assertEqual(titles, ["Úplná záloha Manažera BOZP (*.mbbackup)"])
        self.assertTrue(hasattr(tab, "create_mbbackup_button"))
        self.assertTrue(hasattr(tab, "verify_mbbackup_button"))
        self.assertTrue(hasattr(tab, "restore_mbbackup_button"))
        self.assertTrue(hasattr(tab, "recovery_diag_button"))

    def test_legacy_zip_sections_not_visible(self) -> None:
        tab = BackupTab()
        text = "\n".join(label.text() for label in tab.findChildren(QLabel))
        titles = "\n".join(group.title() for group in tab.findChildren(QGroupBox))
        combined = f"{text}\n{titles}"
        self.assertNotIn("Dřívější formát", combined)
        self.assertNotIn("kompletní ZIP", combined.lower())
        self.assertNotIn("Vytvořit kompletní zálohu", combined)
        self.assertNotIn("Obnovit kompletní zálohu", combined)
        self.assertFalse(hasattr(tab, "create_backup_button"))
        self.assertFalse(hasattr(tab, "restore_backup_button"))
        self.assertFalse(hasattr(tab, "backup_manifest_table"))

    def test_description_mentions_content_without_instance_jargon(self) -> None:
        tab = BackupTab()
        text = "\n".join(label.text() for label in tab.findChildren(QLabel))
        self.assertIn("databázi", text)
        self.assertIn("přílohy", text)
        self.assertIn("číselníky", text)
        self.assertNotIn("instance", text.casefold())

    def test_renders_without_legacy_zip_history(self) -> None:
        # Žádná historie ZIP / sprava_dat.json – záložka se musí vykreslit.
        settings = storage_module.storage_service.config_dir / "sprava_dat.json"
        if settings.exists():
            settings.unlink()
        tab = BackupTab()
        tab.refresh()
        self.assertIsNotNone(tab.create_mbbackup_button)
        self.assertEqual(tab.create_mbbackup_button.text(), "Vytvořit zálohu")

    def test_legacy_zip_service_still_importable(self) -> None:
        self.assertTrue(callable(full_backup_workflow_service.create_full_backup))
        self.assertTrue(callable(full_backup_workflow_service.restore_full_backup))

    def test_sprava_dat_page_backup_tab_label(self) -> None:
        page = SpravaDatPage()
        self.assertEqual(TAB_BACKUP, "Zálohování a obnova")
        self.assertIsInstance(page.backup_tab, BackupTab)


if __name__ == "__main__":
    unittest.main()
