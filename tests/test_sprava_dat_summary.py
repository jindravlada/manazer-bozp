import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QScrollArea, QSplitter, QTabWidget

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.backup_service import BACKUP_TYPE_FULL, backup_service
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        BackupRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.sluzby.data_management_status_service import (
        data_management_status_service,
    )
    from moduly.sprava_dat.ui.backup_tab import BackupTab
    from moduly.sprava_dat.ui.manifest_presenter import rows_from_backup_manifest
    from moduly.sprava_dat.ui.manifest_table_widget import ManifestTableWidget
    from moduly.sprava_dat.ui.summary_tab import SummaryTab
    from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage
    from moduly.sprava_dat.ui.tab_constants import (
        TAB_BACKUP,
        TAB_CODEBOOKS,
        TAB_DIAGNOSTICS,
        TAB_ORDER,
        TAB_SUMMARY,
        TAB_TRANSFER,
    )


class DataManagementStatusServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

    def test_status_requires_attention_without_backup(self) -> None:
        status, warnings = data_management_status_service.compute_status()
        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(any("záloha" in warning.lower() for warning in warnings))
        self.assertTrue(any("diagnostika" in warning.lower() for warning in warnings))

    def test_missing_backup_file_is_problem(self) -> None:
        data_management_settings_service.save_last_backup(
            BackupRecord(
                created_at="2026-07-10T10:00:00",
                path=str(storage_module.storage_service.backups_dir / "missing.zip"),
                manifest={"verified": True},
                backup_type=BACKUP_TYPE_FULL,
            )
        )
        status, warnings = data_management_status_service.compute_status()
        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(any("nebyl nalezen" in warning for warning in warnings))


class SummaryTabTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self.navigated: list[str] = []
        self.tab = SummaryTab(navigate_callback=self.navigated.append)

    def test_shows_attention_without_backup(self) -> None:
        self.tab.refresh()
        self.assertIn("Vyžaduje pozornost", self.tab.status_value.text())
        self.assertIn("záloha", self.tab.warnings_label.text().lower())

    def test_shows_last_backup_details(self) -> None:
        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        manifest = backup_service.verify_backup_integrity(backup_path, backup_type=BACKUP_TYPE_FULL)
        data_management_settings_service.save_last_backup(
            BackupRecord(
                created_at="2026-07-10T12:00:00",
                path=str(backup_path),
                manifest=manifest,
                backup_type=BACKUP_TYPE_FULL,
            )
        )
        self.tab.refresh()
        self.assertIn(backup_path.name, self.tab.backup_summary_label.text())
        self.assertIn("ověřena", self.tab.backup_summary_label.text())

    def test_navigate_buttons_switch_tabs_on_page(self) -> None:
        page = SpravaDatPage()
        page.navigate_to_tab(TAB_TRANSFER)
        tabs = page.findChild(QTabWidget)
        assert tabs is not None
        self.assertEqual(tabs.tabText(tabs.currentIndex()), TAB_TRANSFER)


class SpravaDatPageSummaryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_summary_is_first_and_default_tab(self) -> None:
        page = SpravaDatPage()
        tabs = page.findChild(QTabWidget)
        assert tabs is not None
        self.assertEqual(list(TAB_ORDER), [tabs.tabText(index) for index in range(tabs.count())])
        self.assertEqual(tabs.tabText(tabs.currentIndex()), TAB_SUMMARY)

        page.refresh()
        self.assertEqual(tabs.tabText(tabs.currentIndex()), TAB_SUMMARY)

    def test_navigate_to_tabs(self) -> None:
        page = SpravaDatPage()
        tabs = page.findChild(QTabWidget)
        assert tabs is not None

        for tab_key in (TAB_BACKUP, TAB_TRANSFER, TAB_CODEBOOKS, TAB_DIAGNOSTICS):
            page.navigate_to_tab(tab_key)
            self.assertEqual(tabs.tabText(tabs.currentIndex()), tab_key)


class BackupTabLayoutTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self.tab = BackupTab()

    def test_backup_tab_has_scroll_area_and_splitters(self) -> None:
        self.assertIsNotNone(self.tab.findChild(QScrollArea))
        splitters = self.tab.findChildren(QSplitter)
        self.assertGreaterEqual(len(splitters), 2)
        for splitter in splitters:
            self.assertGreaterEqual(splitter.widget(0).minimumWidth(), 280)
            self.assertGreaterEqual(splitter.widget(1).minimumWidth(), 280)

    def test_manifest_table_loads_from_saved_backup(self) -> None:
        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        manifest = backup_service.verify_backup_integrity(backup_path, backup_type=BACKUP_TYPE_FULL)
        data_management_settings_service.save_last_backup(
            BackupRecord(
                created_at="2026-07-10T12:00:00",
                path=str(backup_path),
                manifest=manifest,
                backup_type=BACKUP_TYPE_FULL,
            )
        )
        self.tab.refresh()

        self.assertGreater(self.tab.backup_manifest_table.rowCount(), 0)
        self.assertEqual(
            self.tab.backup_manifest_table.item(0, 0).text(),
            rows_from_backup_manifest(manifest)[0][0],
        )

    def test_small_window_keeps_controls_available(self) -> None:
        self.tab.show()
        self._app.processEvents()
        self.tab.resize(500, 400)
        self.assertIsNotNone(self.tab.create_backup_button)
        self.assertIsNotNone(self.tab.restore_backup_button)
        scroll = self.tab.findChild(QScrollArea)
        assert scroll is not None
        self.assertTrue(scroll.widgetResizable())


class ManifestTableWidgetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_table_is_read_only_with_three_columns(self) -> None:
        table = ManifestTableWidget()
        table.set_rows([("Databáze aplikace", "manager_bozp.db", "V pořádku")])
        self.assertEqual(table.columnCount(), 3)
        self.assertEqual(table.horizontalHeaderItem(0).text(), "Položka")
        self.assertEqual(table.item(0, 1).text(), "manager_bozp.db")


if __name__ == "__main__":
    unittest.main()
