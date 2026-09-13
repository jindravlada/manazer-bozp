"""SEC-CLEANUP-BACKUP-1: automatické safety backupy jsou ``*.mbbackup``."""

from __future__ import annotations

import importlib
import os
import shutil
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from core.backup.constants import BACKUP_EXTENSION
from core.backup.package_create import InstanceBackupError

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "sec-cleanup-backup-1"
_HOME = _TEST_ROOT / "home"

if _TEST_ROOT.exists():
    shutil.rmtree(_TEST_ROOT)
_HOME.mkdir(parents=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_HOME):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.backup.package_integrity import inspect_backup_integrity
    from core.backup.safety_backup import (
        SAFETY_PREFIX_CODEBOOKS_IMPORT,
        SAFETY_PREFIX_REGISTRY_IMPORT,
        create_verified_application_safety_backup,
    )
    from moduly.pravni_pozadavky.import_export.legal_registry_export_service import (
        legal_registry_export_service,
    )
    from moduly.pravni_pozadavky.import_export.legal_registry_import_service import (
        legal_registry_import_service,
    )
    from moduly.sprava_dat.sluzby.codebook_export_service import codebook_export_service
    from moduly.sprava_dat.sluzby.codebook_manifest_service import (
        MANIFEST_FILENAME,
        codebook_manifest_service,
    )
    from moduly.sprava_dat.sluzby.codebook_transfer_service import codebook_transfer_service
    from moduly.sprava_dat.sluzby.legal_registry_transfer_service import (
        legal_registry_transfer_service,
    )


def _backups_dir() -> Path:
    return storage_module.storage_service.backups_dir


def _assert_mbbackup_safety(path: Path, prefix: str) -> None:
    safety = Path(path)
    assert safety.is_file(), safety
    assert safety.suffix == BACKUP_EXTENSION, safety.name
    assert safety.name.startswith(f"{prefix}-"), safety.name
    report = inspect_backup_integrity(safety)
    assert report.ok, report.to_dict()


class SecCleanupBackup1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        backups = _backups_dir()
        backups.mkdir(parents=True, exist_ok=True)
        for item in backups.glob("*"):
            if item.is_file():
                item.unlink()

    def test_registry_import_creates_mbbackup_not_zip(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "registry-source.json"
        legal_registry_export_service.export_to_file(export_path)

        result = legal_registry_transfer_service.import_with_verified_safety(export_path)

        _assert_mbbackup_safety(
            Path(result["safety_backup_path"]),
            SAFETY_PREFIX_REGISTRY_IMPORT,
        )
        self.assertTrue(result["safety_backup_manifest"].get("verified"))
        self.assertEqual(list(_backups_dir().glob("pred-importem-registru-*.zip")), [])
        self.assertEqual(list(_backups_dir().glob("*.zip")), [])

    def test_codebook_import_creates_mbbackup_not_zip(self) -> None:
        target = storage_module.storage_service.exports_dir / "ciselniky-import.zip"
        codebook_export_service.export_all_codebooks(target)

        result = codebook_transfer_service.import_with_verified_safety(target)

        _assert_mbbackup_safety(
            Path(result["safety_backup_path"]),
            SAFETY_PREFIX_CODEBOOKS_IMPORT,
        )
        self.assertTrue(result["safety_backup_manifest"].get("verified"))
        self.assertEqual(list(_backups_dir().glob("pred-importem-ciselniku-*.zip")), [])
        self.assertEqual(list(_backups_dir().glob("pred-importem-*.zip")), [])

    def test_failed_safety_backup_blocks_registry_import(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "registry-fail.json"
        legal_registry_export_service.export_to_file(export_path)

        with patch(
            "core.backup.safety_backup.create_instance_backup",
            side_effect=InstanceBackupError("disk full"),
        ):
            with patch.object(legal_registry_import_service, "import_from_file") as mock_import:
                with self.assertRaises(ValueError) as ctx:
                    legal_registry_transfer_service.import_with_verified_safety(export_path)
                self.assertIn("Import nebyl spuštěn", str(ctx.exception))
                mock_import.assert_not_called()

        self.assertEqual(list(_backups_dir().glob("pred-importem-registru-*")), [])

    def test_codebook_export_package_remains_zip(self) -> None:
        target = storage_module.storage_service.exports_dir / "ciselniky-package.zip"
        codebook_export_service.export_all_codebooks(target)

        self.assertTrue(target.is_file())
        self.assertEqual(target.suffix, ".zip")
        with zipfile.ZipFile(target, "r") as zf:
            self.assertIn(MANIFEST_FILENAME, zf.namelist())
        verified = codebook_manifest_service.verify_bulk_export(target)
        self.assertTrue(verified.get("verified"))
        self.assertEqual(list(_backups_dir().glob("*.mbbackup")), [])
        self.assertEqual(list(_backups_dir().glob("pred-importem-*.zip")), [])

    def test_helper_writes_only_mbbackup(self) -> None:
        path, manifest = create_verified_application_safety_backup(
            filename_prefix="pred-importem-registru",
            blocked_operation="Import nebyl spuštěn.",
        )
        _assert_mbbackup_safety(path, SAFETY_PREFIX_REGISTRY_IMPORT)
        self.assertTrue(manifest.get("verified"))
        self.assertEqual(manifest.get("backup_format"), "mbbackup")
        self.assertEqual(list(_backups_dir().glob("*.zip")), [])


if __name__ == "__main__":
    unittest.main()
