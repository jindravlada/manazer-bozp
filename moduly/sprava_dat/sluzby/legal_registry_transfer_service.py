from datetime import datetime
from pathlib import Path

from core.services.backup_service import BACKUP_TYPE_FULL, backup_service
from core.services.storage_service import storage_service
from moduly.pravni_pozadavky.import_export.legal_registry_import_service import (
    legal_registry_import_service,
)
from moduly.sprava_dat.sluzby.legal_registry_manifest_service import (
    legal_registry_manifest_service,
)


class LegalRegistryTransferService:
    """Orchestrace importu registru s ověřenou bezpečnostní zálohou."""

    def create_verified_safety_backup(self) -> tuple[Path, dict]:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safety_path = backup_service.create_backup(
            storage_service.backups_dir / f"pred-importem-registru-{timestamp}.zip",
            backup_type=BACKUP_TYPE_FULL,
        )
        manifest = backup_service.verify_backup_integrity(safety_path, backup_type=BACKUP_TYPE_FULL)
        if not manifest.get("verified"):
            errors = manifest.get("verification_errors") or ["Neznámá chyba ověření."]
            try:
                safety_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ValueError(
                "Bezpečnostní záloha se nepodařila ověřit. Import nebyl spuštěn.\n\n"
                + "\n".join(errors)
            )
        return safety_path, manifest

    def import_with_verified_safety(self, source_path: str | Path) -> dict:
        safety_path, safety_manifest = self.create_verified_safety_backup()
        result = legal_registry_import_service.import_from_file(source_path)
        counts = legal_registry_manifest_service.import_result_to_counts(result)
        return {
            "imported_at": datetime.now().isoformat(timespec="seconds"),
            "source_path": str(Path(source_path).resolve()),
            "safety_backup_path": str(safety_path.resolve()),
            "safety_backup_manifest": safety_manifest,
            "record_counts": counts,
            "methodology_warning": (
                "Import registru neobsahuje auditní metodiky. "
                "Pro zachování vazeb v auditech je nutné přenést také odpovídající metodiky."
            ),
        }


legal_registry_transfer_service = LegalRegistryTransferService()
