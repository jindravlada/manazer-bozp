from datetime import datetime
from pathlib import Path

from core.backup.safety_backup import (
    SAFETY_PREFIX_REGISTRY_IMPORT,
    create_verified_application_safety_backup,
)
from moduly.pravni_pozadavky.import_export.legal_registry_import_service import (
    legal_registry_import_service,
)
from moduly.sprava_dat.sluzby.legal_registry_manifest_service import (
    legal_registry_manifest_service,
)


class LegalRegistryTransferService:
    """Orchestrace importu registru s ověřenou bezpečnostní zálohou."""

    def create_verified_safety_backup(self) -> tuple[Path, dict]:
        return create_verified_application_safety_backup(
            filename_prefix=SAFETY_PREFIX_REGISTRY_IMPORT,
            blocked_operation="Import nebyl spuštěn.",
        )

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
