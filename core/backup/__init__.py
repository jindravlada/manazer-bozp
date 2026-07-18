"""Společná infrastruktura formátu záložního balíčku ``*.mbbackup`` (BACKUP-1a).

Tato fáze poskytuje konstanty, bezpečné cesty, SHA-256 a metadata/manifest.
Tvorba obsahu archivu a obnova jsou předmětem pozdějších fází.
"""

from core.backup.constants import (
    BACKUP_EXTENSION,
    BACKUP_FORMAT_VERSION,
    COMPONENT_DATABASE,
    COMPONENT_METADATA,
    COMPONENT_SETTINGS,
    COMPONENT_WORKSPACE,
    METADATA_FILENAME,
    PACKAGE_KIND_INSTANCE_BACKUP,
    PACKAGE_KIND_RISK_CATALOG_EXPORT,
    PACKAGE_STATUS_COMPLETE,
    PACKAGE_STATUS_CREATING,
    REQUIRED_ARCHIVE_ROOTS,
    SUPPORTED_BACKUP_FORMAT_VERSIONS,
    SUPPORTED_PACKAGE_KINDS,
)
from core.backup.hashing import hashes_equal, sha256_bytes, sha256_file, sha256_stream
from core.backup.metadata import (
    BackupFileEntry,
    BackupMetadata,
    BackupMetadataError,
    build_file_entry,
    create_backup_metadata,
    mark_package_complete,
    validate_backup_metadata,
)
from core.backup.paths import (
    BackupPathError,
    component_for_archive_path,
    is_safe_archive_path,
    normalize_archive_path,
)

__all__ = [
    "BACKUP_EXTENSION",
    "BACKUP_FORMAT_VERSION",
    "COMPONENT_DATABASE",
    "COMPONENT_METADATA",
    "COMPONENT_SETTINGS",
    "COMPONENT_WORKSPACE",
    "METADATA_FILENAME",
    "PACKAGE_KIND_INSTANCE_BACKUP",
    "PACKAGE_KIND_RISK_CATALOG_EXPORT",
    "PACKAGE_STATUS_COMPLETE",
    "PACKAGE_STATUS_CREATING",
    "REQUIRED_ARCHIVE_ROOTS",
    "SUPPORTED_BACKUP_FORMAT_VERSIONS",
    "SUPPORTED_PACKAGE_KINDS",
    "BackupFileEntry",
    "BackupMetadata",
    "BackupMetadataError",
    "BackupPathError",
    "build_file_entry",
    "component_for_archive_path",
    "create_backup_metadata",
    "hashes_equal",
    "is_safe_archive_path",
    "mark_package_complete",
    "normalize_archive_path",
    "sha256_bytes",
    "sha256_file",
    "sha256_stream",
    "validate_backup_metadata",
]
