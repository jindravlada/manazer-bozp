"""Důkladná kontrola integrity balíčku ``*.mbbackup`` (BACKUP-1c).

Bez obnovy – pouze ověření použitelnosti balíčku.
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from core.backup.constants import (
    BACKUP_EXTENSION,
    COMPONENT_DATABASE,
    INTEGRITY_INVALID,
    INTEGRITY_VALID,
    INTEGRITY_VALID_WITH_WARNINGS,
    ISSUE_SEVERITY_ERROR,
    ISSUE_SEVERITY_WARNING,
    METADATA_FILENAME,
    PACKAGE_KIND_INSTANCE_BACKUP,
    PACKAGE_STATUS_COMPLETE,
    REQUIRED_ARCHIVE_ROOTS,
    SUPPORTED_BACKUP_FORMAT_VERSIONS,
    SUPPORTED_PACKAGE_KINDS,
)
from core.backup.hashing import hashes_equal, sha256_bytes
from core.backup.metadata import BackupMetadata, BackupMetadataError
from core.backup.paths import BackupPathError, normalize_archive_path
from core.backup.sqlite_snapshot import SqliteSnapshotError, inspect_sqlite_file
from core.backup.workspace_roots import (
    SNAPSHOT_SUPPORT_PHOTOS_LIMITATION,
    package_covers_snapshot_support_photos,
)


class BackupPackageVerificationError(ValueError):
    """Balíček neprošel kontrolou úplnosti / integrity."""


@dataclass(frozen=True)
class BackupIntegrityIssue:
    """Jeden nalezený problém při kontrole zálohy."""

    code: str
    message: str
    severity: str = ISSUE_SEVERITY_ERROR

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class BackupIntegrityReport:
    """
    Souhrnný výsledek kontroly ``*.mbbackup``.

    status:
      - ``VALID``
      - ``VALID_WITH_WARNINGS``
      - ``INVALID``
    """

    status: str
    issues: list[BackupIntegrityIssue] = field(default_factory=list)
    metadata: BackupMetadata | None = None
    package_path: str | None = None
    files_checked: int = 0
    database_integrity: str | None = None
    database_quick_check: str | None = None
    database_size: int | None = None
    database_empty: bool | None = None

    @property
    def ok(self) -> bool:
        """True, pokud je balíček použitelný (VALID nebo VALID_WITH_WARNINGS)."""
        return self.status in (INTEGRITY_VALID, INTEGRITY_VALID_WITH_WARNINGS)

    @property
    def errors(self) -> list[BackupIntegrityIssue]:
        return [i for i in self.issues if i.severity == ISSUE_SEVERITY_ERROR]

    @property
    def warnings(self) -> list[BackupIntegrityIssue]:
        return [i for i in self.issues if i.severity == ISSUE_SEVERITY_WARNING]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "ok": self.ok,
            "package_path": self.package_path,
            "files_checked": self.files_checked,
            "database_integrity": self.database_integrity,
            "database_quick_check": self.database_quick_check,
            "database_size": self.database_size,
            "database_empty": self.database_empty,
            "issues": [issue.to_dict() for issue in self.issues],
            "metadata": self.metadata.to_dict() if self.metadata is not None else None,
        }


def _error(code: str, message: str) -> BackupIntegrityIssue:
    return BackupIntegrityIssue(code=code, message=message, severity=ISSUE_SEVERITY_ERROR)


def _warning(code: str, message: str) -> BackupIntegrityIssue:
    return BackupIntegrityIssue(
        code=code, message=message, severity=ISSUE_SEVERITY_WARNING
    )


def _finalize_status(issues: list[BackupIntegrityIssue]) -> str:
    if any(i.severity == ISSUE_SEVERITY_ERROR for i in issues):
        return INTEGRITY_INVALID
    if any(i.severity == ISSUE_SEVERITY_WARNING for i in issues):
        return INTEGRITY_VALID_WITH_WARNINGS
    return INTEGRITY_VALID


def _check_database_bytes(
    data: bytes,
    *,
    metadata: BackupMetadata | None,
    issues: list[BackupIntegrityIssue],
) -> tuple[str | None, str | None, int | None, bool | None]:
    """Ověří SQLite bajty z archivu; vrací (integrity, quick, size, empty)."""
    size = len(data)
    if size <= 0:
        issues.append(_error("database_empty", "Databáze v záloze má nulovou velikost."))
        return "failed", "failed", 0, True

    tmp_dir = tempfile.mkdtemp(prefix="mbbackup-dbcheck-")
    tmp_db = Path(tmp_dir) / "check.db"
    try:
        tmp_db.write_bytes(data)
        try:
            info = inspect_sqlite_file(tmp_db)
        except SqliteSnapshotError as exc:
            issues.append(_error("database_unreadable", f"Databázi nelze ověřit: {exc}"))
            return None, None, size, None

        integrity = str(info["integrity_check"])
        quick = str(info["quick_check"])
        empty = bool(info["empty"])
        inspected_size = int(info["size"])  # type: ignore[arg-type]

        if metadata is not None and metadata.database_size is not None:
            if metadata.database_size != inspected_size:
                issues.append(
                    _error(
                        "database_size_mismatch",
                        "Velikost DB v metadatech neodpovídá souboru v archivu "
                        f"({metadata.database_size} != {inspected_size}).",
                    )
                )
        if size != inspected_size:
            issues.append(
                _error("database_size_mismatch", "Velikost DB po extrakci nesedí.")
            )

        if integrity != "ok":
            issues.append(
                _error(
                    "database_integrity_failed",
                    f"PRAGMA integrity_check selhal: {integrity}.",
                )
            )
        if quick != "ok":
            issues.append(
                _error(
                    "database_quick_check_failed",
                    f"PRAGMA quick_check selhal: {quick}.",
                )
            )
        if empty:
            issues.append(
                _warning(
                    "database_empty",
                    "Databáze neobsahuje uživatelské tabulky/objekty.",
                )
            )

        if (
            metadata is not None
            and metadata.database_integrity
            and metadata.database_integrity != integrity
            and integrity != "ok"
        ):
            issues.append(
                _warning(
                    "database_integrity_metadata_mismatch",
                    "Uložený database_integrity v metadatech neodpovídá aktuální kontrole.",
                )
            )
        return integrity, quick, inspected_size, empty
    finally:
        try:
            tmp_db.unlink(missing_ok=True)
            Path(tmp_dir).rmdir()
        except OSError:
            pass


def inspect_backup_integrity(
    package_path: str | Path,
    *,
    require_extension: bool = True,
    run_database_checks: bool = True,
) -> BackupIntegrityReport:
    """
    Kompletní kontrola zálohy bez obnovy.

    Vrací ``BackupIntegrityReport`` se statusem VALID / VALID_WITH_WARNINGS / INVALID
    a seznamem problémů. Nevyhazuje výjimku při neplatném balíčku.
    """
    path = Path(package_path)
    issues: list[BackupIntegrityIssue] = []
    metadata: BackupMetadata | None = None
    files_checked = 0
    db_integrity: str | None = None
    db_quick: str | None = None
    db_size: int | None = None
    db_empty: bool | None = None

    if not path.is_file():
        issues.append(_error("file_missing", f"Soubor neexistuje: {path}"))
        return BackupIntegrityReport(
            status=INTEGRITY_INVALID,
            issues=issues,
            package_path=str(path),
        )

    if require_extension and path.suffix.lower() != BACKUP_EXTENSION:
        if not path.name.endswith(BACKUP_EXTENSION + ".partial"):
            issues.append(
                _error(
                    "bad_extension",
                    f"Očekávána přípona {BACKUP_EXTENSION}, dostáno {path.suffix!r}.",
                )
            )

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = list(zf.namelist())
            name_set = set(names)

            if METADATA_FILENAME not in name_set:
                issues.append(
                    _error("missing_metadata", f"V balíčku chybí {METADATA_FILENAME}.")
                )
                return BackupIntegrityReport(
                    status=_finalize_status(issues),
                    issues=issues,
                    package_path=str(path),
                )

            try:
                raw_meta = zf.read(METADATA_FILENAME)
                meta_data = json.loads(raw_meta.decode("utf-8"))
            except zipfile.BadZipFile as exc:
                issues.append(
                    _error("bad_zip", f"Poškozený ZIP při čtení metadata: {exc}")
                )
                return BackupIntegrityReport(
                    status=INTEGRITY_INVALID,
                    issues=issues,
                    package_path=str(path),
                )
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
                issues.append(
                    _error(
                        "invalid_metadata_json",
                        f"Nelze načíst metadata.json: {exc}",
                    )
                )
                return BackupIntegrityReport(
                    status=INTEGRITY_INVALID,
                    issues=issues,
                    package_path=str(path),
                )

            try:
                format_version_int = int(meta_data.get("format_version"))
            except (TypeError, ValueError):
                issues.append(
                    _error(
                        "bad_format_version",
                        f"Neplatná format_version: {meta_data.get('format_version')!r}.",
                    )
                )
            else:
                if format_version_int not in SUPPORTED_BACKUP_FORMAT_VERSIONS:
                    issues.append(
                        _error(
                            "unsupported_format_version",
                            f"Nepodporovaná verze formátu: {format_version_int}.",
                        )
                    )

            package_kind = str(meta_data.get("package_kind", "")).strip()
            if package_kind not in SUPPORTED_PACKAGE_KINDS:
                issues.append(
                    _error("bad_package_kind", f"Neplatný typ balíčku: {package_kind!r}.")
                )
            elif package_kind != PACKAGE_KIND_INSTANCE_BACKUP:
                issues.append(
                    _error(
                        "bad_package_kind",
                        f"Neočekávaný package_kind: {package_kind!r}.",
                    )
                )

            package_status = str(meta_data.get("package_status", "")).strip()
            if package_status != PACKAGE_STATUS_COMPLETE:
                issues.append(
                    _error(
                        "incomplete_package",
                        f"Balíček není ve stavu complete (status={package_status!r}).",
                    )
                )

            try:
                metadata = BackupMetadata.from_dict(meta_data)
            except BackupMetadataError as exc:
                message = str(exc)
                if not any(message in issue.message for issue in issues):
                    issues.append(_error("invalid_metadata", message))

            if metadata is not None:
                covers_photos = package_covers_snapshot_support_photos(
                    included_workspace_roots=metadata.included_workspace_roots,
                    file_paths=[entry.path for entry in metadata.files],
                )
                if not covers_photos:
                    issues.append(
                        _warning(
                            "snapshot_support_photos_uncovered",
                            SNAPSHOT_SUPPORT_PHOTOS_LIMITATION,
                        )
                    )
                if metadata.unknown_workspace_roots:
                    listed = ", ".join(metadata.unknown_workspace_roots)
                    issues.append(
                        _warning(
                            "unknown_workspace_roots",
                            "Úplná záloha je INCOMPLETE: neznámé datové kořeny "
                            f"workspace: {listed}.",
                        )
                    )

            included: list[str] = []
            if metadata is not None:
                included = list(metadata.included_components)
            elif isinstance(meta_data.get("included_components"), list):
                included = [str(c) for c in meta_data["included_components"]]

            for root in REQUIRED_ARCHIVE_ROOTS:
                has_prefix = any(
                    name == root
                    or name.startswith(root + "/")
                    or name.rstrip("/") == root
                    for name in names
                )
                in_components = root in included

                if root == COMPONENT_DATABASE:
                    if not has_prefix:
                        issues.append(
                            _error(
                                "missing_database_dir",
                                "V archivu chybí soubory pod database/.",
                            )
                        )
                    if not in_components:
                        issues.append(
                            _error(
                                "missing_archive_root",
                                f"Chybí povinná komponenta v included_components: {root}.",
                            )
                        )
                    continue

                if not in_components:
                    issues.append(
                        _error(
                            "missing_archive_root",
                            f"Chybí povinná komponenta v included_components: {root}.",
                        )
                    )
                elif not has_prefix:
                    issues.append(
                        _warning(
                            "missing_archive_root_files",
                            f"Komponenta {root} je deklarována, ale v ZIP nejsou soubory.",
                        )
                    )

            files_raw = meta_data.get("files")
            if not isinstance(files_raw, list):
                issues.append(
                    _error("missing_manifest", "Manifest files chybí nebo není seznam.")
                )
                files_raw = []

            seen_paths: set[str] = set()
            db_entries: list[dict] = []

            for item in files_raw:
                if not isinstance(item, dict):
                    issues.append(
                        _error("bad_manifest_entry", "Položka manifestu není objekt.")
                    )
                    continue

                raw_path = str(item.get("path", ""))
                try:
                    archive_path = normalize_archive_path(raw_path)
                except BackupPathError as exc:
                    issues.append(
                        _error(
                            "unsafe_path",
                            f"Nebezpečná cesta v manifestu: {raw_path!r} ({exc})",
                        )
                    )
                    continue

                if archive_path in seen_paths:
                    issues.append(
                        _error(
                            "duplicate_path",
                            f"Duplicitní cesta v manifestu: {archive_path}.",
                        )
                    )
                    continue
                seen_paths.add(archive_path)

                if archive_path not in name_set:
                    issues.append(
                        _error(
                            "missing_file",
                            f"V balíčku chybí soubor z manifestu: {archive_path}.",
                        )
                    )
                    continue

                try:
                    data = zf.read(archive_path)
                except zipfile.BadZipFile as exc:
                    issues.append(
                        _error(
                            "bad_zip",
                            f"Poškozený ZIP při čtení {archive_path}: {exc}",
                        )
                    )
                    continue
                except Exception as exc:  # noqa: BLE001
                    issues.append(
                        _error(
                            "unreadable_file",
                            f"Soubor nelze přečíst z archivu: {archive_path} ({exc}).",
                        )
                    )
                    continue

                files_checked += 1
                try:
                    expected_size_int = int(item.get("size"))
                except (TypeError, ValueError):
                    issues.append(_error("bad_size", f"Neplatná size u {archive_path}."))
                    expected_size_int = None

                if expected_size_int is not None and len(data) != expected_size_int:
                    issues.append(
                        _error(
                            "size_mismatch",
                            f"Neshoda velikosti u {archive_path}: "
                            f"manifest={expected_size_int}, archiv={len(data)}.",
                        )
                    )

                expected_hash = str(item.get("sha256", "")).strip()
                if not hashes_equal(expected_hash, sha256_bytes(data)):
                    issues.append(
                        _error("hash_mismatch", f"Neshoda SHA-256 u {archive_path}.")
                    )

                if str(item.get("component", "")).strip() == COMPONENT_DATABASE:
                    db_entries.append({"path": archive_path, "data": data})

            for name in names:
                if name.endswith("/") or name == METADATA_FILENAME:
                    continue
                try:
                    normalize_archive_path(name)
                except BackupPathError as exc:
                    issues.append(
                        _error(
                            "unsafe_zip_path",
                            f"Nebezpečná cesta v archivu: {name!r} ({exc})",
                        )
                    )

            if not db_entries:
                issues.append(
                    _error(
                        "missing_database",
                        "Manifest/archiv neobsahuje databázový soubor.",
                    )
                )
            elif run_database_checks:
                db_integrity, db_quick, db_size, db_empty = _check_database_bytes(
                    db_entries[0]["data"],
                    metadata=metadata,
                    issues=issues,
                )
    except zipfile.BadZipFile as exc:
        issues.append(_error("bad_zip", f"Poškozený nebo nečitelný ZIP: {exc}"))

    return BackupIntegrityReport(
        status=_finalize_status(issues),
        issues=issues,
        metadata=metadata,
        package_path=str(path),
        files_checked=files_checked,
        database_integrity=db_integrity,
        database_quick_check=db_quick,
        database_size=db_size,
        database_empty=db_empty,
    )


def assert_backup_integrity(
    package_path: str | Path,
    *,
    require_extension: bool = True,
    allow_warnings: bool = True,
) -> BackupIntegrityReport:
    """
    Stejná kontrola jako ``inspect_backup_integrity``, ale při INVALID
    (a volitelně při warnings) vyhodí ``BackupPackageVerificationError``.
    """
    report = inspect_backup_integrity(
        package_path,
        require_extension=require_extension,
    )
    if report.status == INTEGRITY_INVALID:
        messages = "; ".join(i.message for i in report.errors) or "Balíček je neplatný."
        raise BackupPackageVerificationError(messages)
    if not allow_warnings and report.status == INTEGRITY_VALID_WITH_WARNINGS:
        messages = "; ".join(i.message for i in report.warnings) or "Balíček má varování."
        raise BackupPackageVerificationError(messages)
    return report
