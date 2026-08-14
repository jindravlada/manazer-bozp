"""Jednorázová záloha před první změnou metodiky v2 (AUDIT-METHOD-V2b)."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from core.backup.constants import BACKUP_EXTENSION
from core.database.upgrade_guard import (
    PreMigrationBackupError,
    create_verified_pre_migration_backup,
)
from core.services.storage_service import storage_service
from moduly.audity.constants import PRE_AUDIT_METHOD_V2_BACKUP_PREFIX

logger = logging.getLogger(__name__)


class AuditMethodV2BackupError(PreMigrationBackupError):
    """Selhání jednorázové pre-v2 zálohy — změnu neukládat."""


def list_pre_v2_backups(backups_dir: Path | None = None) -> list[Path]:
    root = Path(backups_dir) if backups_dir is not None else storage_service.backups_dir
    if not root.is_dir():
        return []
    return sorted(root.glob(f"{PRE_AUDIT_METHOD_V2_BACKUP_PREFIX}_*{BACKUP_EXTENSION}"))


def pre_v2_backup_exists(*, backups_dir: Path | None = None) -> bool:
    """Ověří existenci zálohy proti skutečnému workspace (ne jen markeru)."""
    return bool(list_pre_v2_backups(backups_dir))


def allocate_pre_v2_backup_path(
    backups_dir: Path | None = None,
    *,
    when: datetime | None = None,
) -> Path:
    root = Path(backups_dir) if backups_dir is not None else storage_service.backups_dir
    root.mkdir(parents=True, exist_ok=True)
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    base = f"{PRE_AUDIT_METHOD_V2_BACKUP_PREFIX}_{stamp}{BACKUP_EXTENSION}"
    candidate = root / base
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        alt = root / (
            f"{PRE_AUDIT_METHOD_V2_BACKUP_PREFIX}_{stamp}_{index}{BACKUP_EXTENSION}"
        )
        if not alt.exists():
            return alt
    raise AuditMethodV2BackupError(
        "Nelze přidělit unikátní název zálohy pre_audit_method_v2."
    )


def ensure_pre_v2_backup(
    *,
    workspace_root: Path | None = None,
    database_path: Path | None = None,
    settings_path: Path | None = None,
    backups_dir: Path | None = None,
) -> Path | None:
    """
    Před první v2 změnou vytvoří ověřenou ``pre_audit_method_v2_*.mbbackup``.

    Další volání vrátí ``None`` (záloha už existuje). Při selhání nevyvolá zápis.
    """
    if pre_v2_backup_exists(backups_dir=backups_dir):
        return None

    storage_service.ensure_structure()
    ws = Path(workspace_root) if workspace_root is not None else storage_service.base
    db = Path(database_path) if database_path is not None else storage_service.database_path
    target = allocate_pre_v2_backup_path(backups_dir, when=datetime.now())
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=ws,
            database_path=db,
            settings_path=settings_path,
        )
    except PreMigrationBackupError as exc:
        raise AuditMethodV2BackupError(str(exc)) from exc
    except Exception as exc:
        raise AuditMethodV2BackupError(
            "Nepodařilo se vytvořit zálohu před první změnou metodiky v2. "
            "Změna nebyla uložena."
        ) from exc

    logger.info("AUDIT-METHOD-V2b: vytvořena pre-v2 záloha: %s", backup_path)
    return backup_path
