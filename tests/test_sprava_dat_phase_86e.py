import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton

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
    from moduly.pravni_pozadavky.import_export.legal_registry_export_service import (
        legal_registry_export_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_registry_diagnostic_service import (
        legal_registry_diagnostic_service,
    )
    from moduly.pravni_pozadavky.ui.legal_registry_diagnostic_actions import (
        persist_diagnostic_result,
        show_legal_registry_diagnostic,
    )
    from moduly.pravni_pozadavky.ui.pravni_pozadavky_requirements_tab import (
        PravniPozadavkyRequirementsTab,
    )
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        BackupRecord,
        RegistryExportRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.sluzby.legal_registry_manifest_service import (
        legal_registry_manifest_service,
    )
    from moduly.sprava_dat.ui.legal_registry_diagnostics_tab import LegalRegistryDiagnosticsTab
    from moduly.sprava_dat.ui.legal_registry_transfer_tab import LegalRegistryTransferTab


class RppToolbarPhase86eTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_backup_and_restore_buttons_removed_from_ui(self) -> None:
        tab = PravniPozadavkyRequirementsTab()
        button_texts = [button.text() for button in tab.findChildren(QPushButton)]
        self.assertNotIn("Záloha registru", button_texts)
        self.assertNotIn("Obnovit registr", button_texts)
        self.assertIn("Diagnostika registru", button_texts)

    def test_export_and_restore_methods_remain_available(self) -> None:
        tab = PravniPozadavkyRequirementsTab()
        self.assertTrue(callable(tab.export_registry_configuration))
        self.assertTrue(callable(tab.restore_registry_configuration))


class RegistryDiagnosticSharedTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

    def test_diagnostic_persists_result(self) -> None:
        result = legal_registry_diagnostic_service.run()
        persist_diagnostic_result(result)

        stored = data_management_settings_service.get_last_diagnostic()
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertIn("summary", stored)
        self.assertIn("created_at", stored)

    def test_diagnostic_from_sprava_dat_uses_same_service(self) -> None:
        diagnostics_tab = LegalRegistryDiagnosticsTab()
        with patch(
            "moduly.sprava_dat.ui.legal_registry_diagnostics_tab.show_legal_registry_diagnostic",
            return_value=legal_registry_diagnostic_service.run(),
        ) as mock_show:
            diagnostics_tab._run_diagnostic()
        mock_show.assert_called_once_with(diagnostics_tab)

    def test_diagnostic_from_rpp_uses_shared_action(self) -> None:
        tab = PravniPozadavkyRequirementsTab()
        with patch(
            "moduly.pravni_pozadavky.ui.pravni_pozadavky_requirements_tab.show_legal_registry_diagnostic",
            return_value=legal_registry_diagnostic_service.run(),
        ) as mock_show:
            tab.show_registry_diagnostic()
        mock_show.assert_called_once_with(tab)


class LegalRegistryTransferTabPhase86eTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self.tab = LegalRegistryTransferTab()

    def test_card_shows_checkmarks_and_updated_warning(self) -> None:
        from PySide6.QtWidgets import QLabel

        all_text = "\n".join(label.text() for label in self.tab.findChildren(QLabel))
        self.assertIn("✔ Právní předpisy", all_text)
        self.assertIn("✖ Auditní metodiky", all_text)
        self.assertIn("✖ Registr rizik", all_text)
        self.assertIn(
            "Pokud nejsou přeneseny auditní metodiky, budou procesy existovat",
            all_text,
        )

    def test_export_manifest_table_matches_record_counts(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "manifest-table.json"
        legal_registry_export_service.export_to_file(export_path)
        manifest = legal_registry_manifest_service.verify_export_file(export_path)
        data_management_settings_service.save_last_registry_export(
            RegistryExportRecord(
                created_at="2026-07-10T12:00:00",
                path=str(export_path),
                manifest=manifest,
            )
        )
        self.tab.refresh()

        self.assertGreater(self.tab.export_manifest_table.rowCount(), 0)
        self.assertEqual(
            self.tab.export_manifest_table.item(0, 0).text(),
            "Právní předpisy",
        )
        self.assertEqual(
            self.tab.export_manifest_table.item(0, 1).text(),
            str(manifest["record_counts"]["documents"]),
        )

    def test_import_saves_pre_import_backup_record(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "import-86e.json"
        legal_registry_export_service.export_to_file(export_path)

        with patch(
            "moduly.sprava_dat.ui.legal_registry_transfer_tab.QFileDialog.getOpenFileName",
            return_value=(str(export_path), ""),
        ):
            with patch(
                "moduly.sprava_dat.ui.legal_registry_transfer_tab.QMessageBox.warning",
                return_value=__import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.StandardButton.Yes,
            ):
                with patch("moduly.sprava_dat.ui.legal_registry_transfer_tab.QMessageBox.information"):
                    self.tab._import_registry()

        pre_import = data_management_settings_service.get_last_registry_pre_import_backup()
        self.assertIsNotNone(pre_import)
        assert pre_import is not None
        self.assertTrue(Path(pre_import.path).is_file())
        self.assertTrue(pre_import.manifest.get("verified"))


if __name__ == "__main__":
    unittest.main()
