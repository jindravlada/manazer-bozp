import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QTabWidget

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
    from moduly.sprava_dat.ui.legal_registry_diagnostics_tab import LegalRegistryDiagnosticsTab
    from moduly.sprava_dat.ui.process_requirements_developer_actions import (
        confirm_and_delete_all_process_requirements,
    )
    from moduly.sprava_dat.ui.tab_constants import TAB_DIAGNOSTICS
    from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage


class NastaveniMaintenancePhase91bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_settings_page_has_no_maintenance_tab(self) -> None:
        page = NastaveniPage()
        tabs = page.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        assert tabs is not None

        tab_labels = [tabs.tabText(index) for index in range(tabs.count())]
        self.assertNotIn("Údržba", tab_labels)

    def test_settings_page_has_no_delete_process_requirements_button(self) -> None:
        page = NastaveniPage()
        buttons = page.findChildren(QPushButton)
        button_texts = [button.text() for button in buttons]
        self.assertNotIn("Vymazat všechny procesní požadavky", button_texts)
        self.assertNotIn("Smazat všechny řídicí procesy", button_texts)


class SpravaDatDiagnosticsPhase91bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_diagnostics_tab_contains_developer_delete_button(self) -> None:
        tab = LegalRegistryDiagnosticsTab()
        button_texts = [button.text() for button in tab.findChildren(QPushButton)]
        self.assertIn("Smazat všechny řídicí procesy", button_texts)

    def test_sprava_dat_exposes_delete_only_in_diagnostics_tab(self) -> None:
        page = SpravaDatPage()
        tabs = page.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        assert tabs is not None

        diagnostics_index = tabs.indexOf(page.diagnostics_tab)
        self.assertGreaterEqual(diagnostics_index, 0)
        self.assertEqual(tabs.tabText(diagnostics_index), TAB_DIAGNOSTICS)

        for index in range(tabs.count()):
            tabs.setCurrentIndex(index)
            current = tabs.currentWidget()
            assert current is not None
            button_texts = [button.text() for button in current.findChildren(QPushButton)]
            if index == diagnostics_index:
                self.assertIn("Smazat všechny řídicí procesy", button_texts)
            else:
                self.assertNotIn("Smazat všechny řídicí procesy", button_texts)


class ProcessRequirementsDeveloperActionsPhase91bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    @patch(
        "moduly.sprava_dat.ui.process_requirements_developer_actions.legal_requirement_service.delete_all_process_requirements"
    )
    @patch("moduly.sprava_dat.ui.process_requirements_developer_actions.QMessageBox.information")
    @patch("moduly.sprava_dat.ui.process_requirements_developer_actions.QMessageBox.critical")
    @patch("moduly.sprava_dat.ui.process_requirements_developer_actions.QMessageBox.warning")
    def test_requires_double_confirmation_before_delete(
        self,
        mock_warning,
        mock_critical,
        _mock_information,
        mock_delete,
    ) -> None:
        mock_warning.return_value = QMessageBox.Yes
        mock_critical.return_value = QMessageBox.No
        mock_delete.return_value = {
            "requirements": 1,
            "sources": 2,
            "checks": 3,
            "sanctions": 4,
        }

        result = confirm_and_delete_all_process_requirements()

        self.assertFalse(result)
        mock_warning.assert_called_once()
        mock_critical.assert_called_once()
        mock_delete.assert_not_called()

    @patch(
        "moduly.sprava_dat.ui.process_requirements_developer_actions.legal_requirement_service.delete_all_process_requirements"
    )
    @patch("moduly.sprava_dat.ui.process_requirements_developer_actions.QMessageBox.information")
    @patch("moduly.sprava_dat.ui.process_requirements_developer_actions.QMessageBox.critical")
    @patch("moduly.sprava_dat.ui.process_requirements_developer_actions.QMessageBox.warning")
    def test_deletes_only_after_both_confirmations(
        self,
        mock_warning,
        mock_critical,
        _mock_information,
        mock_delete,
    ) -> None:
        mock_warning.return_value = QMessageBox.Yes
        mock_critical.return_value = QMessageBox.Yes
        mock_delete.return_value = {
            "requirements": 1,
            "sources": 2,
            "checks": 3,
            "sanctions": 4,
        }

        result = confirm_and_delete_all_process_requirements()

        self.assertTrue(result)
        mock_delete.assert_called_once()


if __name__ == "__main__":
    unittest.main()
