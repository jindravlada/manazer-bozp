"""Automatická bezpečnostní záloha instance před rizikovou operací.

APPLICATION SAFETY BACKUP = ``*.mbbackup`` přes ``create_instance_backup``.
Nepoužívá legacy ZIP ``BackupService.create_backup``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.backup.constants import BACKUP_EXTENSION
from core.backup.package_create import InstanceBackupError, create_instance_backup
from core.backup.package_integrity import inspect_backup_integrity

SAFETY_PREFIX_REGISTRY_IMPORT = "pred-importem-registru"
SAFETY_PREFIX_CODEBOOKS_IMPORT = "pred-importem-ciselniku"
SAFETY_PREFIX_BEFORE_RESTORE = "pred-obnovou"


def allocate_application_safety_backup_path(
    filename_prefix: str,
    backups_dir: Path,
) -> Path:
    """Jednoznačný název; nikdy nepřepisuje existující soubor."""
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    candidate = backups_dir / f"{filename_prefix}-{stamp}{BACKUP_EXTENSION}"
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        alt = backups_dir / f"{filename_prefix}-{stamp}-{index}{BACKUP_EXTENSION}"
        if not alt.exists():
            return alt
    raise InstanceBackupError("Nelze přidělit unikátní název bezpečnostní zálohy.")


def create_verified_application_safety_backup(
    *,
    filename_prefix: str,
    blocked_operation: str,
    backups_dir: Path | None = None,
) -> tuple[Path, dict]:
    """Vytvoří a ověří bezpečnostní ``*.mbbackup`` aktuálního workspace.

    Při chybě vytvoření nebo ověření soubor smaže (pokud vznikl) a vyvolá
    ``ValueError``. Volající nesmí spustit destruktivní operaci.
    """
    from core.services.storage_service import storage_service

    storage_service.ensure_structure()
    target_dir = Path(backups_dir) if backups_dir is not None else storage_service.backups_dir
    target = allocate_application_safety_backup_path(filename_prefix, target_dir)

    try:
        result = create_instance_backup(
            target,
            workspace_root=storage_service.base,
            database_path=storage_service.database_path,
            verify=True,
        )
    except (InstanceBackupError, OSError) as exc:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise ValueError(
            "Bezpečnostní záloha se nepodařila vytvořit. "
            f"{blocked_operation}\n\n{exc}"
        ) from exc

    report = inspect_backup_integrity(target)
    if not report.ok:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        details = "; ".join(issue.message for issue in report.issues[:5])
        raise ValueError(
            "Bezpečnostní záloha se nepodařila ověřit. "
            f"{blocked_operation}\n\n"
            + (details or report.status or "Neznámá chyba ověření.")
        )

    manifest: dict = {
        "verified": True,
        "backup_format": "mbbackup",
        "status": report.status,
        "ok": True,
        "package_path": str(target.resolve()),
        "files_checked": report.files_checked,
        "database_integrity": report.database_integrity,
        "coverage_verdict": result.coverage_verdict,
        "verification_errors": [],
    }
    return Path(result.path).resolve(), manifest
