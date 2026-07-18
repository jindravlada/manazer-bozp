"""Datový model metadata.json a validace formátu *.mbbackup."""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from core.backup.constants import (
    BACKUP_FORMAT_VERSION,
    COMPONENT_METADATA,
    METADATA_FILENAME,
    PACKAGE_KIND_INSTANCE_BACKUP,
    PACKAGE_STATUS_COMPLETE,
    PACKAGE_STATUS_CREATING,
    REQUIRED_ARCHIVE_ROOTS,
    SUPPORTED_BACKUP_FORMAT_VERSIONS,
    SUPPORTED_PACKAGE_KINDS,
    VALID_PACKAGE_STATUSES,
)
from core.backup.paths import BackupPathError, normalize_archive_path
from core.version import APP_VERSION


class BackupMetadataError(ValueError):
    """Neplatná metadata záložního balíčku."""


@dataclass(frozen=True)
class BackupFileEntry:
    """Jedna položka manifestu souborů v balíčku."""

    path: str
    component: str
    size: int
    sha256: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "component": self.component,
            "size": self.size,
            "sha256": self.sha256,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BackupFileEntry":
        if not isinstance(data, Mapping):
            raise BackupMetadataError("Položka manifestu musí být objekt.")
        try:
            path = normalize_archive_path(str(data.get("path", "")))
        except BackupPathError as exc:
            raise BackupMetadataError(str(exc)) from exc

        component = str(data.get("component", "")).strip()
        if not component:
            raise BackupMetadataError(f"Chybí component u souboru {path!r}.")

        try:
            size = int(data["size"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BackupMetadataError(f"Neplatná size u souboru {path!r}.") from exc
        if size < 0:
            raise BackupMetadataError(f"Záporná size u souboru {path!r}.")

        sha256 = str(data.get("sha256", "")).strip().lower()
        if not sha256 or len(sha256) != 64:
            raise BackupMetadataError(f"Neplatný sha256 u souboru {path!r}.")
        if any(c not in "0123456789abcdef" for c in sha256):
            raise BackupMetadataError(f"Neplatný sha256 u souboru {path!r}.")

        required = bool(data.get("required", True))
        return cls(
            path=path,
            component=component,
            size=size,
            sha256=sha256,
            required=required,
        )


@dataclass
class BackupMetadata:
    """
    Metadata balíčku ``*.mbbackup`` (soubor metadata.json).

    Neukládá citlivé firemní ani osobní údaje.
    """

    format_version: int
    created_at: str
    app_version: str
    package_kind: str
    package_status: str
    platform: str
    included_components: list[str]
    files: list[BackupFileEntry]
    total_content_size: int
    database_integrity: str | None = None
    schema_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "created_at": self.created_at,
            "app_version": self.app_version,
            "schema_version": self.schema_version,
            "platform": self.platform,
            "package_kind": self.package_kind,
            "included_components": list(self.included_components),
            "files": [entry.to_dict() for entry in self.files],
            "total_content_size": self.total_content_size,
            "database_integrity": self.database_integrity,
            "package_status": self.package_status,
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent) + (
            "\n" if indent is not None else ""
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BackupMetadata":
        if not isinstance(data, Mapping):
            raise BackupMetadataError("Metadata musí být JSON objekt.")
        _require_keys(
            data,
            (
                "format_version",
                "created_at",
                "app_version",
                "platform",
                "package_kind",
                "included_components",
                "files",
                "total_content_size",
                "package_status",
            ),
        )

        try:
            format_version = int(data["format_version"])
        except (TypeError, ValueError) as exc:
            raise BackupMetadataError("Neplatná format_version.") from exc

        created_at = str(data["created_at"]).strip()
        if not created_at:
            raise BackupMetadataError("Chybí created_at.")

        app_version = str(data["app_version"]).strip()
        if not app_version:
            raise BackupMetadataError("Chybí app_version.")

        package_kind = str(data["package_kind"]).strip()
        package_status = str(data["package_status"]).strip()
        platform_name = str(data["platform"]).strip()
        if not platform_name:
            raise BackupMetadataError("Chybí platform.")

        components_raw = data["included_components"]
        if not isinstance(components_raw, list) or not components_raw:
            raise BackupMetadataError("included_components musí být neprázdný seznam.")
        included_components = [str(c).strip() for c in components_raw]
        if any(not c for c in included_components):
            raise BackupMetadataError("included_components obsahuje prázdnou položku.")

        files_raw = data["files"]
        if not isinstance(files_raw, list):
            raise BackupMetadataError("files musí být seznam.")
        files = [BackupFileEntry.from_dict(item) for item in files_raw]

        try:
            total_content_size = int(data["total_content_size"])
        except (TypeError, ValueError) as exc:
            raise BackupMetadataError("Neplatná total_content_size.") from exc
        if total_content_size < 0:
            raise BackupMetadataError("total_content_size nesmí být záporná.")

        schema_version = data.get("schema_version")
        if schema_version is not None:
            schema_version = str(schema_version).strip() or None

        database_integrity = data.get("database_integrity")
        if database_integrity is not None:
            database_integrity = str(database_integrity).strip() or None

        meta = cls(
            format_version=format_version,
            created_at=created_at,
            app_version=app_version,
            package_kind=package_kind,
            package_status=package_status,
            platform=platform_name,
            included_components=included_components,
            files=files,
            total_content_size=total_content_size,
            database_integrity=database_integrity,
            schema_version=schema_version,
        )
        validate_backup_metadata(meta)
        return meta

    @classmethod
    def from_json(cls, text: str) -> "BackupMetadata":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BackupMetadataError(f"Neplatný JSON metadat: {exc}") from exc
        return cls.from_dict(data)


def _require_keys(data: Mapping[str, Any], keys: Sequence[str]) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise BackupMetadataError(
            "Chybí povinná pole: " + ", ".join(missing)
        )


def utc_now_iso() -> str:
    """Aktuální čas UTC ve formátu ISO 8601 s offsetem."""
    return datetime.now(timezone.utc).isoformat()


def detect_platform_label() -> str:
    """Identifikátor platformy vytvoření (bez citlivých údajů)."""
    return f"{sys.platform}/{platform.machine()}"


def create_backup_metadata(
    *,
    files: Sequence[BackupFileEntry] | None = None,
    included_components: Sequence[str] | None = None,
    package_status: str = PACKAGE_STATUS_CREATING,
    package_kind: str = PACKAGE_KIND_INSTANCE_BACKUP,
    format_version: int = BACKUP_FORMAT_VERSION,
    app_version: str | None = None,
    schema_version: str | None = None,
    database_integrity: str | None = None,
    created_at: str | None = None,
    platform_name: str | None = None,
    validate: bool = True,
) -> BackupMetadata:
    """
    Vytvoří objekt metadat.

    Výchozí stav je ``creating`` (nedokončený balíček). Platný balíček musí mít
    ``package_status=complete`` a projít ``validate_backup_metadata``.
    """
    file_list = list(files or ())
    components = list(
        included_components
        if included_components is not None
        else list(REQUIRED_ARCHIVE_ROOTS)
    )
    total = sum(entry.size for entry in file_list)

    meta = BackupMetadata(
        format_version=format_version,
        created_at=created_at or utc_now_iso(),
        app_version=app_version or APP_VERSION,
        package_kind=package_kind,
        package_status=package_status,
        platform=platform_name or detect_platform_label(),
        included_components=components,
        files=file_list,
        total_content_size=total,
        database_integrity=database_integrity,
        schema_version=schema_version,
    )
    if validate:
        # Při creating povolíme i prázdný manifest; při complete musí být validní.
        if package_status == PACKAGE_STATUS_COMPLETE:
            validate_backup_metadata(meta)
        else:
            validate_backup_metadata(meta, require_complete=False)
    return meta


def validate_backup_metadata(
    meta: BackupMetadata,
    *,
    require_complete: bool = True,
) -> None:
    """
    Validuje metadata balíčku.

    Při ``require_complete=True`` (výchozí) musí být stav ``complete``.
    """
    if meta.format_version not in SUPPORTED_BACKUP_FORMAT_VERSIONS:
        raise BackupMetadataError(
            f"Nepodporovaná verze formátu zálohy: {meta.format_version}."
        )

    if meta.package_kind not in SUPPORTED_PACKAGE_KINDS:
        raise BackupMetadataError(
            f"Nepodporovaný typ balíčku: {meta.package_kind!r}."
        )

    if meta.package_status not in VALID_PACKAGE_STATUSES:
        raise BackupMetadataError(
            f"Neplatný package_status: {meta.package_status!r}."
        )

    if require_complete and meta.package_status != PACKAGE_STATUS_COMPLETE:
        raise BackupMetadataError(
            "Balíček není dokončený (package_status musí být 'complete')."
        )

    if not str(meta.created_at).strip():
        raise BackupMetadataError("Chybí created_at.")
    if not str(meta.app_version).strip():
        raise BackupMetadataError("Chybí app_version.")
    if not str(meta.platform).strip():
        raise BackupMetadataError("Chybí platform.")

    if not meta.included_components:
        raise BackupMetadataError("included_components nesmí být prázdný.")

    for root in REQUIRED_ARCHIVE_ROOTS:
        if root not in meta.included_components:
            raise BackupMetadataError(
                f"Chybí povinná komponenta v included_components: {root}."
            )

    seen: set[str] = set()
    computed_total = 0
    for entry in meta.files:
        try:
            path = normalize_archive_path(entry.path)
        except BackupPathError as exc:
            raise BackupMetadataError(str(exc)) from exc
        if path != entry.path:
            raise BackupMetadataError(
                f"Cesta v manifestu není normalizovaná: {entry.path!r}."
            )
        if path in seen:
            raise BackupMetadataError(f"Duplicitní cesta v manifestu: {path!r}.")
        seen.add(path)

        if not entry.component.strip():
            raise BackupMetadataError(f"Chybí component u souboru {path!r}.")
        if entry.size < 0:
            raise BackupMetadataError(f"Záporná size u souboru {path!r}.")
        if len(entry.sha256) != 64:
            raise BackupMetadataError(f"Neplatný sha256 u souboru {path!r}.")

        # metadata.json samotný nemá být v files (je vedle obsahu), ale pokud je,
        # komponenta metadata je v pořádku.
        if entry.component == COMPONENT_METADATA and path != METADATA_FILENAME:
            raise BackupMetadataError(
                f"Komponenta metadata smí obsahovat jen {METADATA_FILENAME}."
            )

        computed_total += entry.size

    if meta.total_content_size != computed_total:
        raise BackupMetadataError(
            "total_content_size neodpovídá součtu velikostí v manifestu "
            f"({meta.total_content_size} != {computed_total})."
        )


def mark_package_complete(meta: BackupMetadata) -> BackupMetadata:
    """Vrátí kopii metadat se stavem complete a přepočítanou total_content_size."""
    files = list(meta.files)
    return BackupMetadata(
        format_version=meta.format_version,
        created_at=meta.created_at,
        app_version=meta.app_version,
        package_kind=meta.package_kind,
        package_status=PACKAGE_STATUS_COMPLETE,
        platform=meta.platform,
        included_components=list(meta.included_components),
        files=files,
        total_content_size=sum(f.size for f in files),
        database_integrity=meta.database_integrity,
        schema_version=meta.schema_version,
    )


def build_file_entry(
    path: str,
    *,
    component: str,
    size: int,
    sha256: str,
    required: bool = True,
) -> BackupFileEntry:
    """Vytvoří položku manifestu s normalizovanou cestou."""
    normalized = normalize_archive_path(path)
    return BackupFileEntry(
        path=normalized,
        component=component,
        size=size,
        sha256=sha256.strip().lower(),
        required=required,
    )
