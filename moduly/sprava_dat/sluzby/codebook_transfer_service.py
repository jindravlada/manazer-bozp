from datetime import datetime
from pathlib import Path

from core.backup.safety_backup import (
    SAFETY_PREFIX_CODEBOOKS_IMPORT,
    create_verified_application_safety_backup,
)
from moduly.sprava_dat.sluzby.codebook_import_service import codebook_import_service


class CodebookTransferService:
    """Orchestrace hromadného importu číselníků s ověřenou bezpečnostní zálohou."""

    def create_verified_safety_backup(self) -> tuple[Path, dict]:
        return create_verified_application_safety_backup(
            filename_prefix=SAFETY_PREFIX_CODEBOOKS_IMPORT,
            blocked_operation="Import nebyl spuštěn.",
        )

    def import_with_verified_safety(self, source_path: str | Path) -> dict:
        safety_path, safety_manifest = self.create_verified_safety_backup()
        summary = codebook_import_service.import_all_codebooks(source_path)
        return {
            "imported_at": datetime.now().isoformat(timespec="seconds"),
            "source_path": str(Path(source_path).resolve()),
            "safety_backup_path": str(safety_path.resolve()),
            "safety_backup_manifest": safety_manifest,
            "import_result": summary.to_dict(),
        }

    def import_group_with_verified_safety(self, module: str, source_path: str | Path) -> dict:
        safety_path, safety_manifest = self.create_verified_safety_backup()
        summary = codebook_import_service.import_group_codebooks(module, source_path)
        return {
            "imported_at": datetime.now().isoformat(timespec="seconds"),
            "source_path": str(Path(source_path).resolve()),
            "group_module": module,
            "safety_backup_path": str(safety_path.resolve()),
            "safety_backup_manifest": safety_manifest,
            "import_result": summary.to_dict(),
        }


codebook_transfer_service = CodebookTransferService()
