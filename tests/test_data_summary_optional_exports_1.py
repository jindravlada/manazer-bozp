"""DATA-SUMMARY-OPTIONAL-EXPORTS-1: chybějící soubor úspěšného exportu nesníží stav dat."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp(prefix="data-summary-optional-exports-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.backup.completeness import (
        VERDICT_COMPLETE_WITH_LIMITATIONS,
        VERDICT_INCOMPLETE,
    )
    from core.backup.constants import BACKUP_EXTENSION, INTEGRITY_VALID_WITH_WARNINGS
    from core.backup.workspace_roots import (
        SNAPSHOT_SUPPORT_PHOTOS_LIMITATION,
        UNKNOWN_ROOTS_MESSAGE_PREFIX,
    )
    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        BACKUP_TYPE_INSTANCE,
        BackupRecord,
        CodebooksExportRecord,
        CodebooksImportRecord,
        RegistryExportRecord,
        RegistryImportRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.sluzby.data_management_status_service import (
        data_management_status_service,
    )
    from moduly.sprava_dat.ui.summary_tab import SummaryTab


MISSING_EXPORT_WARNINGS = (
    "Soubor posledního exportu registru nebyl nalezen.",
    "Soubor posledního exportu číselníků nebyl nalezen.",
)
CARD_EXPORT_MISSING = "poslední export – soubor nenalezen"


def _backup_path(name: str = "verified") -> Path:
    return storage_module.storage_service.backups_dir / f"{name}{BACKUP_EXTENSION}"


def _save_verified_backup(*, name: str = "verified", **manifest_extra) -> BackupRecord:
    path = _backup_path(name)
    path.write_bytes(b"mbbackup")
    record = BackupRecord(
        created_at="2026-09-04T10:00:00",
        path=str(path),
        manifest={
            "verified": True,
            "backup_format": "mbbackup",
            **manifest_extra,
        },
        backup_type=BACKUP_TYPE_INSTANCE,
    )
    data_management_settings_service.save_last_backup(record)
    return record


def _save_registry_export(*, verified: bool, path: str) -> RegistryExportRecord:
    record = RegistryExportRecord(
        created_at="2026-09-04T11:00:00",
        path=path,
        manifest={"verified": verified, "record_counts": {"documents": 1}},
    )
    data_management_settings_service.save_last_registry_export(record)
    return record


def _save_codebooks_export(*, verified: bool, path: str) -> CodebooksExportRecord:
    record = CodebooksExportRecord(
        created_at="2026-09-04T11:30:00",
        path=path,
        manifest={"verified": verified},
        export_type="bulk",
    )
    data_management_settings_service.save_last_codebooks_export(record)
    return record


def _missing_path(name: str) -> str:
    return str(storage_module.storage_service.exports_dir / name)


class OptionalExportStatusTestCase(unittest.TestCase):
    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

    def test_verified_backup_missing_registry_export_is_ok(self) -> None:
        _save_verified_backup()
        _save_registry_export(verified=True, path=_missing_path("rpp-missing.json"))

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "V pořádku")
        self.assertEqual(warnings, [])
        self.assertEqual(
            data_management_status_service.registry_status_text(),
            CARD_EXPORT_MISSING,
        )

    def test_verified_backup_missing_codebooks_export_is_ok(self) -> None:
        _save_verified_backup()
        _save_codebooks_export(verified=True, path=_missing_path("ciselniky-missing.zip"))

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "V pořádku")
        self.assertEqual(warnings, [])
        self.assertEqual(
            data_management_status_service.codebooks_status_text(),
            CARD_EXPORT_MISSING,
        )

    def test_verified_backup_both_exports_missing_is_ok(self) -> None:
        _save_verified_backup()
        _save_registry_export(verified=True, path=_missing_path("rpp-missing.json"))
        _save_codebooks_export(verified=True, path=_missing_path("ciselniky-missing.zip"))

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "V pořádku")
        self.assertEqual(warnings, [])
        for phrase in MISSING_EXPORT_WARNINGS:
            self.assertNotIn(phrase, warnings)

    def test_missing_complete_backup_requires_attention(self) -> None:
        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(any("záloha" in item.lower() for item in warnings))

    def test_unverified_backup_requires_attention(self) -> None:
        path = _backup_path("unverified")
        path.write_bytes(b"mbbackup")
        data_management_settings_service.save_last_backup(
            BackupRecord(
                created_at="2026-09-04T10:00:00",
                path=str(path),
                manifest={"verified": False, "backup_format": "mbbackup"},
                backup_type=BACKUP_TYPE_INSTANCE,
            )
        )

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(any("nebyla ověřena" in item for item in warnings))
        self.assertEqual(data_management_status_service.backup_status_text(), "neověřena")

    def test_failed_export_is_not_confused_with_later_missing_file(self) -> None:
        _save_verified_backup()
        _save_registry_export(verified=False, path=_missing_path("rpp-failed.json"))
        _save_codebooks_export(verified=True, path=_missing_path("ciselniky-moved.zip"))

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(any("export registru nebyl ověřen" in item for item in warnings))
        self.assertFalse(any(item in MISSING_EXPORT_WARNINGS for item in warnings))
        self.assertFalse(any("exportu číselníků" in item for item in warnings))
        self.assertEqual(
            data_management_status_service.registry_status_text(),
            "poslední export – neověřen",
        )
        self.assertEqual(
            data_management_status_service.codebooks_status_text(),
            CARD_EXPORT_MISSING,
        )

    def test_failed_import_is_not_confused_with_missing_export_file(self) -> None:
        _save_verified_backup()
        _save_registry_export(verified=True, path=_missing_path("rpp-moved.json"))
        data_management_settings_service.save_last_codebooks_import(
            CodebooksImportRecord(
                created_at="2026-09-04T12:00:00",
                source_path=_missing_path("import.zip"),
                safety_backup_path=str(_backup_path("safety-import")),
                import_result={"error_count": 2, "errors": ["selhalo"]},
            )
        )
        _backup_path("safety-import").write_bytes(b"mbbackup")

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(any("import číselníků se nezdařil" in item for item in warnings))
        self.assertFalse(any(item in MISSING_EXPORT_WARNINGS for item in warnings))
        self.assertEqual(
            data_management_status_service.registry_status_text(),
            CARD_EXPORT_MISSING,
        )

    def test_incomplete_backup_remains_a_problem(self) -> None:
        _save_verified_backup(
            coverage_verdict=VERDICT_INCOMPLETE,
            unknown_workspace_roots=["cizi_koren"],
        )
        _save_registry_export(verified=True, path=_missing_path("rpp-missing.json"))

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(any(UNKNOWN_ROOTS_MESSAGE_PREFIX in item for item in warnings))
        self.assertTrue(any("cizi_koren" in item for item in warnings))
        self.assertFalse(any(item in MISSING_EXPORT_WARNINGS for item in warnings))
        self.assertEqual(data_management_status_service.backup_status_text(), "neúplná")

    def test_valid_with_warnings_backup_is_not_damaged(self) -> None:
        _save_verified_backup(
            coverage_verdict=VERDICT_COMPLETE_WITH_LIMITATIONS,
            integrity_status=INTEGRITY_VALID_WITH_WARNINGS,
        )

        status, warnings = data_management_status_service.compute_status()

        self.assertEqual(status, "V pořádku")
        self.assertEqual(warnings, [])
        self.assertEqual(
            data_management_status_service.backup_status_text(),
            "ověřena s omezením",
        )
        self.assertEqual(
            data_management_status_service.backup_limitation_text(),
            SNAPSHOT_SUPPORT_PHOTOS_LIMITATION,
        )


class OptionalExportSummaryUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self.tab = SummaryTab(navigate_callback=lambda _key: None)

    def test_cards_keep_local_missing_export_info(self) -> None:
        _save_verified_backup()
        _save_registry_export(verified=True, path=_missing_path("rpp-missing.json"))
        _save_codebooks_export(verified=True, path=_missing_path("ciselniky-missing.zip"))

        self.tab.refresh()

        self.assertIn("Stav dat: V pořádku", self.tab.status_value.text())
        self.assertIn(
            f"Stav poslední operace: {CARD_EXPORT_MISSING}",
            self.tab.registry_summary_label.text(),
        )
        self.assertIn(
            f"Stav poslední operace: {CARD_EXPORT_MISSING}",
            self.tab.codebooks_summary_label.text(),
        )

    def test_main_reasons_do_not_list_missing_exports(self) -> None:
        _save_verified_backup()
        _save_registry_export(verified=True, path=_missing_path("rpp-missing.json"))
        _save_codebooks_export(verified=True, path=_missing_path("ciselniky-missing.zip"))

        self.tab.refresh()

        reasons = self.tab.warnings_label.text()
        self.assertIn("Všechny známé operace jsou v pořádku", reasons)
        self.assertNotIn("exportu registru", reasons)
        self.assertNotIn("exportu číselníků", reasons)
        self.assertNotIn("soubor nenalezen", reasons.lower())

    def test_opening_summary_does_not_write(self) -> None:
        _save_verified_backup()
        export = _save_registry_export(
            verified=True,
            path=_missing_path("rpp-missing.json"),
        )
        codebooks = _save_codebooks_export(
            verified=True,
            path=_missing_path("ciselniky-missing.zip"),
        )
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
            data_management_settings_service.get_last_registry_export(),
            export,
        )
        self.assertEqual(
            data_management_settings_service.get_last_codebooks_export(),
            codebooks,
        )
        self.assertFalse(
            Path(_missing_path("rpp-missing.json")).exists(),
        )

    def test_valid_with_warnings_shows_limitation_not_damage(self) -> None:
        _save_verified_backup(
            coverage_verdict=VERDICT_COMPLETE_WITH_LIMITATIONS,
            integrity_status=INTEGRITY_VALID_WITH_WARNINGS,
        )
        self.tab.refresh()

        self.assertIn("Stav dat: V pořádku", self.tab.status_value.text())
        self.assertIn("ověřena s omezením", self.tab.backup_summary_label.text())
        self.assertIn(
            SNAPSHOT_SUPPORT_PHOTOS_LIMITATION,
            self.tab.backup_summary_label.text(),
        )
        self.assertIn("není poškozený", self.tab.backup_summary_label.text())
        self.assertNotIn("Vyžaduje pozornost", self.tab.status_value.text())


if __name__ == "__main__":
    unittest.main()
