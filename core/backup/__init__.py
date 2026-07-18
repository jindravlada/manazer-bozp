"""Společná infrastruktura formátu a tvorby záložního balíčku ``*.mbbackup``.

BACKUP-1a: konstanty, cesty, SHA-256, metadata.
BACKUP-1b: vytvoření úplné zálohy instance (bez obnovy a bez UI).
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
from core.backup.package_create import (
    DEFAULT_WORKSPACE_EXCLUDE_DIRS,
    DEFAULT_WORKSPACE_INCLUDE_DIRS,
    CreateInstanceBackupResult,
    InstanceBackupError,
    create_instance_backup,
    default_instance_backup_filename,
)
from core.backup.package_verify import (
    BackupPackageVerificationError,
    package_looks_like_mbbackup,
    read_backup_metadata_from_package,
    verify_instance_backup_package,
)
from core.backup.paths import (
    BackupPathError,
    component_for_archive_path,
    is_safe_archive_path,
    normalize_archive_path,
)
from core.backup.sqlite_snapshot import (
    SqliteSnapshotError,
    create_sqlite_snapshot,
    read_sqlite_user_version,
    sqlite_integrity_check,
)

__all__ = [
    "BACKUP_EXTENSION",
    "BACKUP_FORMAT_VERSION",
    "COMPONENT_DATABASE",
    "COMPONENT_METADATA",
    "COMPONENT_SETTINGS",
    "COMPONENT_WORKSPACE",
    "DEFAULT_WORKSPACE_EXCLUDE_DIRS",
    "DEFAULT_WORKSPACE_INCLUDE_DIRS",
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
    "BackupPackageVerificationError",
    "BackupPathError",
    "CreateInstanceBackupResult",
    "InstanceBackupError",
    "SqliteSnapshotError",
    "build_file_entry",
    "component_for_archive_path",
    "create_backup_metadata",
    "create_instance_backup",
    "create_sqlite_snapshot",
    "default_instance_backup_filename",
    "hashes_equal",
    "is_safe_archive_path",
    "mark_package_complete",
    "normalize_archive_path",
    "package_looks_like_mbbackup",
    "read_backup_metadata_from_package",
    "read_sqlite_user_version",
    "sha256_bytes",
    "sha256_file",
    "sha256_stream",
    "sqlite_integrity_check",
    "validate_backup_metadata",
    "verify_instance_backup_package",
]
