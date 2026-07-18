"""Ověření hotového balíčku ``*.mbbackup`` (metadata, manifest, SHA-256)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from core.backup.constants import (
    BACKUP_EXTENSION,
    COMPONENT_DATABASE,
    METADATA_FILENAME,
    PACKAGE_KIND_INSTANCE_BACKUP,
    PACKAGE_STATUS_COMPLETE,
)
from core.backup.hashing import hashes_equal, sha256_bytes
from core.backup.metadata import BackupMetadata, BackupMetadataError, validate_backup_metadata
from core.backup.paths import BackupPathError, normalize_archive_path


class BackupPackageVerificationError(ValueError):
    """Balíček neprošel kontrolou úplnosti / integrity."""


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
    Ověří platný dokončený ``*.mbbackup``:

    - přípona (volitelně),
    - metadata a stav ``complete``,
    - typ ``instance_backup``,
    - existence všech souborů z manifestu,
    - velikosti a SHA-256,
    - přítomnost databázového snapshotu.
    """
    path = Path(package_path)
    if require_extension and path.suffix.lower() != BACKUP_EXTENSION:
        raise BackupPackageVerificationError(
            f"Očekávána přípona {BACKUP_EXTENSION}, dostáno {path.suffix!r}."
        )

    metadata = read_backup_metadata_from_package(path)
    validate_backup_metadata(metadata, require_complete=True)

    if metadata.package_kind != PACKAGE_KIND_INSTANCE_BACKUP:
        raise BackupPackageVerificationError(
            f"Neočekávaný package_kind: {metadata.package_kind!r}."
        )
    if metadata.package_status != PACKAGE_STATUS_COMPLETE:
        raise BackupPackageVerificationError("Balíček není ve stavu complete.")

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = set(zf.namelist())
            if METADATA_FILENAME not in names:
                raise BackupPackageVerificationError(
                    f"V balíčku chybí {METADATA_FILENAME}."
                )

            db_entries = [
                entry
                for entry in metadata.files
                if entry.component == COMPONENT_DATABASE
            ]
            if not db_entries:
                raise BackupPackageVerificationError(
                    "Manifest neobsahuje žádný soubor komponenty database."
                )

            for entry in metadata.files:
                try:
                    archive_path = normalize_archive_path(entry.path)
                except BackupPathError as exc:
                    raise BackupPackageVerificationError(str(exc)) from exc

                if archive_path not in names:
                    raise BackupPackageVerificationError(
                        f"V balíčku chybí soubor z manifestu: {archive_path}."
                    )

                info = zf.getinfo(archive_path)
                data = zf.read(archive_path)
                if info.file_size != entry.size or len(data) != entry.size:
                    raise BackupPackageVerificationError(
                        f"Neshoda velikosti u {archive_path}: "
                        f"manifest={entry.size}, archiv={len(data)}."
                    )
                actual = sha256_bytes(data)
                if not hashes_equal(entry.sha256, actual):
                    raise BackupPackageVerificationError(
                        f"Neshoda SHA-256 u {archive_path}."
                    )

            # Žádné nebezpečné cesty ve zbytku ZIP
            for name in names:
                if name.endswith("/"):
                    continue
                if name == METADATA_FILENAME:
                    continue
                try:
                    normalize_archive_path(name)
                except BackupPathError as exc:
                    raise BackupPackageVerificationError(
                        f"Nebezpečná cesta v archivu: {name!r} ({exc})"
                    ) from exc
    except zipfile.BadZipFile as exc:
        raise BackupPackageVerificationError(f"Poškozený ZIP/mbbackup: {exc}") from exc

    return metadata


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
