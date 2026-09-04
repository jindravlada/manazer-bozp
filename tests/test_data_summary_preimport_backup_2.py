"""DATA-SUMMARY-PREIMPORT-BACKUP-2: chybějící předimportní záloha RPP po novější úplné záloze."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp(prefix="data-summary-preimport-backup-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.backup.constants import BACKUP_EXTENSION
    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        BACKUP_TYPE_INSTANCE,
        BackupRecord,
        RegistryImportRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.sluzby.data_management_status_service import (
        data_management_status_service,
    )
    from moduly.sprava_dat.ui.legal_registry_transfer_tab import LegalRegistryTransferTab
    from moduly.sprava_dat.ui.summary_tab import SummaryTab


MISSING_PREIMPORT_WARNING = (
    "Bezpečnostní záloha před importem registru nebyla nalezena."
)
CARD_IMPORT_MISSING_SAFETY = "poslední import – chybí bezpečnostní záloha"
IMPORT_AT = "2026-07-10T12:00:00"
BACKUP_AT = "2026-09-04T10:00:00"


def _backup_path(name: str = "verified") -> Path:
    return storage_module.storage_service.backups_dir / f"{name}{BACKUP_EXTENSION}"


def _save_verified_backup(*, created_at: str = BACKUP_AT, name: str = "verified") -> BackupRecord:
    path = _backup_path(name)
    path.write_bytes(b"mbbackup")
    record = BackupRecord(
        created_at=created_at,
        path=str(path),
        manifest={"verified": True, "backup_format": "mbbackup"},
        backup_type=BACKUP_TYPE_INSTANCE,
    )
    data_management_settings_service.save_last_backup(record)
    return record


def _missing_safety_path() -> str:
    return str(
        storage_module.storage_service.backups_dir / f"pred-importem-registru{BACKUP_EXTENSION}"
    )


def _successful_import_result(safety_path: str) -> dict:
    return {
        "imported_at": IMPORT_AT,
        "source_path": str(storage_module.storage_service.exports_dir / "rpp.json"),
        "safety_backup_path": safety_path,
        "record_counts": {"documents": 3, "requirements": 12},
    }


def _save_registry_import(
    *,
    import_result: dict | None = None,
    created_at: str = IMPORT_AT,
    safety_path: str | None = None,
) -> RegistryImportRecord:
    path = safety_path if safety_path is not None else _missing_safety_path()
    record = RegistryImportRecord(
        created_at=created_at,
        source_path=str(storage_module.storage_service.exports_dir / "rpp.json"),
        safety_backup_path=path,
        import_result=_successful_import_result(path) if import_result is None else import_result,
    )
    data_management_settings_service.save_last_registry_import(record)
    return record


def _save_consistent_diagnostic() -> None:
    data_management_settings_service.save_last_diagnostic(
        {
            "created_at": "2026-09-04T09:00:00",
            "summary": "Registr je konzistentní.",
            "issue_count": 0,
            "is_consistent": True,
        }
    )


class PreimportBackupStatusTestCase(unittest.TestCase):
    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

    def test_screen_successful_import_missing_preimport_newer_backup_is_ok(self) -> None:
        _save_verified_backup(created_at=BACKUP_AT)
        _save_registry_import()
        _save_consistent_diagnostic()

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "V pořádku")
        self.assertEqual(warnings, [])
        self.assertNotIn(MISSING_PREIMPORT_WARNING, warnings)
        self.assertEqual(
            data_management_status_service.registry_status_text(),
            CARD_IMPORT_MISSING_SAFETY,
        )
        self.assertEqual(
            data_management_settings_service.format_timestamp(IMPORT_AT),
            "10.07.2026 12:00:00",
        )
        self.assertEqual(
            data_management_settings_service.format_timestamp(BACKUP_AT),
            "04.09.2026 10:00:00",
        )

    def test_mixed_naive_and_aware_timestamps_do_not_crash(self) -> None:
        _save_verified_backup(created_at="2026-09-04T10:00:00+02:00")
        _save_registry_import(created_at="2026-07-10T12:00:00")
        _save_consistent_diagnostic()

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "V pořádku")
        self.assertEqual(warnings, [])

    def test_older_complete_backup_keeps_attention(self) -> None:
        _save_verified_backup(created_at="2026-07-01T08:00:00")
        _save_registry_import()
        _save_consistent_diagnostic()

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertIn(MISSING_PREIMPORT_WARNING, warnings)

    def test_missing_verified_backup_keeps_attention(self) -> None:
        _save_registry_import()
        _save_consistent_diagnostic()

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertIn(MISSING_PREIMPORT_WARNING, warnings)

    def test_failed_import_keeps_attention(self) -> None:
        _save_verified_backup()
        _save_registry_import(
            import_result={"success": False, "error_count": 1, "errors": ["selhalo"]}
        )
        _save_consistent_diagnostic()

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(any("import registru se nezdařil" in item for item in warnings))

    def test_unknown_import_result_keeps_attention(self) -> None:
        _save_verified_backup()
        _save_registry_import(import_result={})
        _save_consistent_diagnostic()

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertIn(MISSING_PREIMPORT_WARNING, warnings)

    def test_incomplete_import_result_keeps_attention(self) -> None:
        _save_verified_backup()
        _save_registry_import(import_result={"imported_at": IMPORT_AT})
        _save_consistent_diagnostic()

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertIn(MISSING_PREIMPORT_WARNING, warnings)

    def test_inconsistent_diagnostic_keeps_attention(self) -> None:
        _save_verified_backup()
        _save_registry_import()
        data_management_settings_service.save_last_diagnostic(
            {
                "created_at": "2026-09-04T09:00:00",
                "summary": "Nalezeno 2 problémů.",
                "issue_count": 2,
                "is_consistent": False,
            }
        )

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(any("nekonzistence" in item for item in warnings))
        self.assertIn(MISSING_PREIMPORT_WARNING, warnings)


class PreimportBackupSummaryUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self.tab = SummaryTab(navigate_callback=lambda _key: None)

    def test_screen_summary_is_ok_and_keeps_import_card_info(self) -> None:
        _save_verified_backup(created_at=BACKUP_AT)
        import_record = _save_registry_import()
        _save_consistent_diagnostic()

        self.tab.refresh()

        self.assertIn("Stav dat: V pořádku", self.tab.status_value.text())
        self.assertNotIn("Bezpečnostní záloha před importem", self.tab.warnings_label.text())
        self.assertIn("Všechny známé operace jsou v pořádku", self.tab.warnings_label.text())
        self.assertIn("10.07.2026", self.tab.registry_summary_label.text())
        self.assertIn("04.09.2026", self.tab.backup_summary_label.text())
        self.assertIn(
            f"Stav poslední operace: {CARD_IMPORT_MISSING_SAFETY}",
            self.tab.registry_summary_label.text(),
        )
        self.assertIn("Registr je konzistentní.", self.tab.diagnostics_summary_label.text())

        transfer = LegalRegistryTransferTab()
        self.assertIn("Bezpečnostní záloha nebyla nalezena.", transfer.last_import_label.text())
        self.assertEqual(
            data_management_settings_service.get_last_registry_import(),
            import_record,
        )
        self.assertFalse(Path(import_record.safety_backup_path).exists())

    def test_opening_summary_does_not_write(self) -> None:
        _save_verified_backup(created_at=BACKUP_AT)
        import_record = _save_registry_import()
        _save_consistent_diagnostic()
        settings_path = data_management_settings_service.settings_path()
        before = settings_path.read_bytes()

        with patch.object(
            data_management_settings_service,
            "_save",
            side_effect=AssertionError("Souhrn nesmí zapisovat sprava_dat.json"),
        ):
            self.tab.refresh()

        self.assertEqual(settings_path.read_bytes(), before)
        self.assertEqual(
            data_management_settings_service.get_last_registry_import(),
            import_record,
        )
        self.assertFalse(Path(_missing_safety_path()).exists())


if __name__ == "__main__":
    unittest.main()
