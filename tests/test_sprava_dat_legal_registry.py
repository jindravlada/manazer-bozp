import importlib
import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

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
    from moduly.pravni_pozadavky.import_export.legal_registry_import_service import (
        legal_registry_import_service,
    )
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        RegistryExportRecord,
        RegistryImportRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.sluzby.legal_registry_manifest_service import (
        legal_registry_manifest_service,
    )
    from moduly.sprava_dat.sluzby.legal_registry_transfer_service import (
        legal_registry_transfer_service,
    )
    from moduly.sprava_dat.ui.legal_registry_transfer_tab import LegalRegistryTransferTab
    from moduly.ukoly.sluzby.task_service import task_service


class LegalRegistryManifestServiceTestCase(unittest.TestCase):
    def test_included_and_excluded_lists_are_visible_constants(self) -> None:
        self.assertIn("Právní předpisy", legal_registry_manifest_service.INCLUDED_ITEMS)
        self.assertIn("Auditní metodiky", legal_registry_manifest_service.EXCLUDED_ITEMS)
        self.assertIn("ID řídicích procesů", legal_registry_manifest_service.LINKS_WARNING)

    def test_manifest_matches_record_counts(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "registry-test.json"
        legal_registry_export_service.export_to_file(export_path)
        manifest = legal_registry_manifest_service.verify_export_file(export_path)

        loaded = json.loads(export_path.read_text(encoding="utf-8"))
        self.assertTrue(manifest["verified"])
        self.assertEqual(manifest["record_counts"], loaded["record_counts"])

    def test_unreadable_json_is_not_verified(self) -> None:
        broken = storage_module.storage_service.exports_dir / "broken.json"
        broken.write_text("{not-json", encoding="utf-8")

        manifest = legal_registry_manifest_service.verify_export_file(broken)

        self.assertFalse(manifest["verified"])


class LegalRegistryTransferServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

    def test_import_creates_verified_safety_backup(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "import-source.json"
        legal_registry_export_service.export_to_file(export_path)

        result = legal_registry_transfer_service.import_with_verified_safety(export_path)

        self.assertTrue(Path(result["safety_backup_path"]).is_file())
        self.assertTrue(result["safety_backup_manifest"].get("verified"))
        self.assertIn("record_counts", result)

    def test_failed_safety_backup_blocks_import(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "import-source-2.json"
        legal_registry_export_service.export_to_file(export_path)

        with patch.object(
            legal_registry_transfer_service,
            "create_verified_safety_backup",
            side_effect=ValueError("Bezpečnostní záloha se nepodařila ověřit."),
        ):
            with patch.object(legal_registry_import_service, "import_from_file") as mock_import:
                with self.assertRaises(ValueError):
                    legal_registry_transfer_service.import_with_verified_safety(export_path)
                mock_import.assert_not_called()

    def test_import_does_not_change_data_outside_registry(self) -> None:
        task = task_service.create_task(title="Úkol mimo registr", description="Zůstane")
        export_path = storage_module.storage_service.exports_dir / "import-source-3.json"
        legal_registry_export_service.export_to_file(export_path)

        legal_registry_transfer_service.import_with_verified_safety(export_path)

        restored_task = task_service.get_task_by_id(task.id)
        self.assertIsNotNone(restored_task)
        assert restored_task is not None
        self.assertEqual(restored_task.title, "Úkol mimo registr")


class LegalRegistryTransferTabTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self.tab = LegalRegistryTransferTab()

    def test_card_lists_included_and_excluded_content(self) -> None:
        all_text = "\n".join(label.text() for label in self.tab.findChildren(QLabel))
        self.assertIn("Obsahuje:", all_text)
        self.assertIn("Neobsahuje:", all_text)
        self.assertIn("✔ Právní předpisy", all_text)
        self.assertIn("✖ Auditní metodiky", all_text)
        self.assertIn("Import registru zachovává původní ID řídicích procesů.", all_text)

    def test_export_uses_existing_service_and_persists(self) -> None:
        target = storage_module.storage_service.exports_dir / "sprava-dat-export.json"

        with patch(
            "moduly.sprava_dat.ui.legal_registry_transfer_tab.QFileDialog.getSaveFileName",
            return_value=(str(target), ""),
        ):
            with patch("moduly.sprava_dat.ui.legal_registry_transfer_tab.QMessageBox.information"):
                self.tab._export_registry()

        record = data_management_settings_service.get_last_registry_export()
        self.assertIsNotNone(record)
        assert record is not None
        self.assertTrue(Path(record.path).is_file())
        self.assertTrue(record.manifest.get("verified"))

        self.tab.refresh()
        self.assertIn(target.name, self.tab.last_export_label.text())

    def test_failed_export_verification_is_not_saved(self) -> None:
        target = storage_module.storage_service.exports_dir / "invalid-export.json"

        with patch(
            "moduly.sprava_dat.ui.legal_registry_transfer_tab.QFileDialog.getSaveFileName",
            return_value=(str(target), ""),
        ):
            with patch(
                "moduly.sprava_dat.ui.legal_registry_transfer_tab.legal_registry_export_service.export_to_file",
                return_value=mock.MagicMock(),
            ):
                with patch(
                    "moduly.sprava_dat.ui.legal_registry_transfer_tab.legal_registry_manifest_service.verify_export_file",
                    return_value={"verified": False, "verification_errors": ["test"]},
                ):
                    with patch("moduly.sprava_dat.ui.legal_registry_transfer_tab.QMessageBox.critical"):
                        self.tab._export_registry()

        self.assertIsNone(data_management_settings_service.get_last_registry_export())

    def test_import_persists_last_import_with_safety_backup(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "import-ui-source.json"
        legal_registry_export_service.export_to_file(export_path)

        with patch(
            "moduly.sprava_dat.ui.legal_registry_transfer_tab.QFileDialog.getOpenFileName",
            return_value=(str(export_path), ""),
        ):
            with patch(
                "moduly.sprava_dat.ui.legal_registry_transfer_tab.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                with patch("moduly.sprava_dat.ui.legal_registry_transfer_tab.QMessageBox.information"):
                    self.tab._import_registry()

        record = data_management_settings_service.get_last_registry_import()
        self.assertIsNotNone(record)
        assert record is not None
        self.assertTrue(Path(record.safety_backup_path).is_file())
        self.assertEqual(record.source_path, str(export_path.resolve()))

        reloaded_tab = LegalRegistryTransferTab()
        self.assertIn(export_path.name, reloaded_tab.last_import_label.text())

    def test_open_export_location_uses_saved_path(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "open-export.json"
        legal_registry_export_service.export_to_file(export_path)
        data_management_settings_service.save_last_registry_export(
            RegistryExportRecord(
                created_at="2026-07-10T12:00:00",
                path=str(export_path),
                manifest={"verified": True, "record_counts": {"documents": 0}},
            )
        )

        with patch(
            "moduly.sprava_dat.ui.legal_registry_transfer_tab.open_path_in_file_manager",
            return_value=True,
        ) as mock_open:
            self.tab._open_export_location()

        mock_open.assert_called_once_with(
            str(export_path),
            parent=self.tab,
            title="Umístění exportu",
        )


class DataManagementRegistrySettingsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

    def test_registry_export_and_import_persist(self) -> None:
        export_record = RegistryExportRecord(
            created_at="2026-07-10T10:00:00",
            path="/tmp/export.json",
            manifest={"record_counts": {"documents": 2}},
        )
        import_record = RegistryImportRecord(
            created_at="2026-07-10T11:00:00",
            source_path="/tmp/import.json",
            safety_backup_path="/tmp/safety.zip",
            import_result={"record_counts": {"documents": 2}},
        )
        data_management_settings_service.save_last_registry_export(export_record)
        data_management_settings_service.save_last_registry_import(import_record)

        loaded_export = data_management_settings_service.get_last_registry_export()
        loaded_import = data_management_settings_service.get_last_registry_import()
        self.assertEqual(loaded_export.path, export_record.path)
        self.assertEqual(loaded_import.safety_backup_path, import_record.safety_backup_path)


if __name__ == "__main__":
    unittest.main()
