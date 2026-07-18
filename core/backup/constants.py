"""Společný formát záložního balíčku Manažera BOZP (BACKUP-1a).

Verze formátu a identifikátory balíčku. Bez UI a bez tvorby/obnovy obsahu.
"""

from __future__ import annotations

# Verze formátu *.mbbackup (metadata.format_version).
BACKUP_FORMAT_VERSION = 1

# Podporované verze při načítání (zpětná kompatibilita).
SUPPORTED_BACKUP_FORMAT_VERSIONS: frozenset[int] = frozenset({BACKUP_FORMAT_VERSION})

BACKUP_EXTENSION = ".mbbackup"
METADATA_FILENAME = "metadata.json"

# Typ balíčku – instance vs. budoucí knowledge exporty.
PACKAGE_KIND_INSTANCE_BACKUP = "instance_backup"
PACKAGE_KIND_RISK_CATALOG_EXPORT = "risk_catalog_export"  # rezervováno, neimplementováno

SUPPORTED_PACKAGE_KINDS: frozenset[str] = frozenset({PACKAGE_KIND_INSTANCE_BACKUP})

# Stav dokončení balíčku.
PACKAGE_STATUS_CREATING = "creating"
PACKAGE_STATUS_COMPLETE = "complete"

VALID_PACKAGE_STATUSES: frozenset[str] = frozenset(
    {
        PACKAGE_STATUS_CREATING,
        PACKAGE_STATUS_COMPLETE,
    }
)

# Povinné kořenové komponenty / adresáře ve formátu v1.
COMPONENT_DATABASE = "database"
COMPONENT_WORKSPACE = "workspace"
COMPONENT_SETTINGS = "settings"
COMPONENT_METADATA = "metadata"

REQUIRED_ARCHIVE_ROOTS: tuple[str, ...] = (
    COMPONENT_DATABASE,
    COMPONENT_WORKSPACE,
    COMPONENT_SETTINGS,
)

KNOWN_COMPONENTS: frozenset[str] = frozenset(
    {
        COMPONENT_DATABASE,
        COMPONENT_WORKSPACE,
        COMPONENT_SETTINGS,
        COMPONENT_METADATA,
    }
)

# Souhrnný výsledek kontroly integrity (BACKUP-1c).
INTEGRITY_VALID = "VALID"
INTEGRITY_VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
INTEGRITY_INVALID = "INVALID"

INTEGRITY_STATUSES: frozenset[str] = frozenset(
    {
        INTEGRITY_VALID,
        INTEGRITY_VALID_WITH_WARNINGS,
        INTEGRITY_INVALID,
    }
)

ISSUE_SEVERITY_ERROR = "error"
ISSUE_SEVERITY_WARNING = "warning"

# Diagnostické kódy obnovy (BACKUP-2a).
RESTORE_ERR_BAD_ARCHIVE = "bad_archive"
RESTORE_ERR_INVALID_METADATA = "invalid_metadata"
RESTORE_ERR_INVALID_DATABASE = "invalid_database"
RESTORE_ERR_MISSING_COMPONENT = "missing_component"
RESTORE_ERR_DISK_FULL = "disk_full"
RESTORE_ERR_WRITE_ERROR = "write_error"
RESTORE_ERR_INTERRUPTED = "interrupted"
RESTORE_ERR_INTEGRITY = "integrity_failed"
RESTORE_ERR_POSTCHECK = "post_restore_check_failed"
RESTORE_ERR_UNSAFE_PATH = "unsafe_path"

# Fázové kódy obnovy (BACKUP-2b).
RESTORE_ERR_FAILED_BEFORE_SWAP = "failed_before_swap"
RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK = "failed_after_swap_rolled_back"
RESTORE_ERR_ROLLBACK_FAILED = "rollback_failed"

# Recovery marker.
RESTORE_MARKER_KIND = "instance_restore"
RESTORE_MARKER_FORMAT_VERSION = 1
RESTORE_MARKER_FILENAME_PREFIX = ".mbrestore-in-progress-"
