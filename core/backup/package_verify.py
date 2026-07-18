"""Ověření hotového balíčku ``*.mbbackup`` (tenká obálka nad BACKUP-1c)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from core.backup.constants import METADATA_FILENAME
from core.backup.metadata import BackupMetadata, BackupMetadataError
from core.backup.package_integrity import (
    BackupPackageVerificationError,
    assert_backup_integrity,
    inspect_backup_integrity,
)


def read_backup_metadata_from_package(package_path: str | Path) -> BackupMetadata:
    """Načte a zvaliduje ``metadata.json`` z balíčku (stav musí být complete)."""
    path = Path(package_path)
    if not path.is_file():
        raise BackupPackageVerificationError(f"Soubor neexistuje: {path}")

    try:
        with zipfile.ZipFile(path, "r") as zf:
            try:
                raw = zf.read(METADATA_FILENAME)
            except KeyError as exc:
                raise BackupPackageVerificationError(
                    f"V balíčku chybí {METADATA_FILENAME}."
                ) from exc
    except zipfile.BadZipFile as exc:
        raise BackupPackageVerificationError(f"Poškozený ZIP/mbbackup: {exc}") from exc

    try:
        return BackupMetadata.from_json(raw.decode("utf-8"))
    except (UnicodeDecodeError, BackupMetadataError) as exc:
        raise BackupPackageVerificationError(str(exc)) from exc


def verify_instance_backup_package(
    package_path: str | Path,
    *,
    require_extension: bool = True,
) -> BackupMetadata:
    """
    Ověří platný dokončený ``*.mbbackup`` (přísný režim).

    Používá ``inspect_backup_integrity``; při ``INVALID`` vyhodí
    ``BackupPackageVerificationError``. Varování jsou povolena.
    """
    report = assert_backup_integrity(
        package_path,
        require_extension=require_extension,
        allow_warnings=True,
    )
    if report.metadata is None:
        raise BackupPackageVerificationError(
            "Balíček neobsahuje použitelná metadata po kontrole integrity."
        )
    return report.metadata


def package_looks_like_mbbackup(package_path: str | Path) -> bool:
    """Rychlá kontrola: ZIP + metadata.json se daří načíst jako JSON objekt."""
    path = Path(package_path)
    if not path.is_file():
        return False
    try:
        with zipfile.ZipFile(path, "r") as zf:
            raw = zf.read(METADATA_FILENAME)
        data = json.loads(raw.decode("utf-8"))
        return isinstance(data, dict) and "package_kind" in data
    except Exception:
        return False


__all__ = [
    "BackupPackageVerificationError",
    "inspect_backup_integrity",
    "package_looks_like_mbbackup",
    "read_backup_metadata_from_package",
    "verify_instance_backup_package",
]
