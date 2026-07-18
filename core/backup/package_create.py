"""Vytvoření úplné zálohy instance ve formátu ``*.mbbackup`` (BACKUP-1b).

Bez UI a bez obnovy – pouze interní API.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.backup.constants import (
    BACKUP_EXTENSION,
    COMPONENT_DATABASE,
    COMPONENT_SETTINGS,
    COMPONENT_WORKSPACE,
    METADATA_FILENAME,
    PACKAGE_STATUS_COMPLETE,
    PACKAGE_STATUS_CREATING,
    REQUIRED_ARCHIVE_ROOTS,
)
from core.backup.hashing import sha256_file
from core.backup.metadata import (
    BackupFileEntry,
    BackupMetadata,
    build_file_entry,
    create_backup_metadata,
    mark_package_complete,
)
from core.backup.package_verify import (
    BackupPackageVerificationError,
    verify_instance_backup_package,
)
from core.backup.paths import normalize_archive_path
from core.backup.sqlite_snapshot import (
    SqliteSnapshotError,
    create_sqlite_snapshot,
    inspect_sqlite_file,
    read_sqlite_user_version,
)

# Adresáře workspace (A+B z BACKUP-0) mapované pod archive ``workspace/``.
DEFAULT_WORKSPACE_INCLUDE_DIRS: tuple[str, ...] = (
    "prilohy",
    "control_results",
    "ciselniky",
    "templates",
    "konfigurace",
)

# Provozní / dočasná data (D) – nikdy do úplné zálohy.
DEFAULT_WORKSPACE_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        "zalohy",
        "import",
        "logy",
        "export",
        "databaze",  # DB jde přes backup API do database/
    }
)

DATABASE_ARCHIVE_NAME = "database/manager_bozp.db"
PARTIAL_SUFFIX = ".partial"

ProgressCallback = Callable[[str], None]
InterruptHook = Callable[[str], None]


class InstanceBackupError(RuntimeError):
    """Chyba při vytváření úplné zálohy instance."""


@dataclass
class CreateInstanceBackupResult:
    """Výsledek úspěšného vytvoření ``*.mbbackup``."""

    path: Path
    metadata: BackupMetadata
    verified: bool = True
    database_integrity: str = "ok"
    staging_dir: Path | None = None
    partial_path_used: Path | None = None


@dataclass
class _StagedFile:
    source: Path
    archive_path: str
    component: str
    required: bool = True


def default_instance_backup_filename(timestamp: str | None = None) -> str:
    """Výchozí název souboru zálohy (bez adresáře)."""
    from datetime import datetime

    stamp = timestamp or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return f"manazer-bozp-instance-{stamp}{BACKUP_EXTENSION}"


def resolve_settings_file(settings_path: Path | None = None) -> Path | None:
    """Vrátí existující soubor UI nastavení, nebo ``None``."""
    if settings_path is not None:
        return settings_path if settings_path.is_file() else None
    try:
        from core.settings.settings_manager import settings as settings_manager

        candidate = Path(settings_manager.file)
    except Exception:
        candidate = Path("data/nastaveni/settings.json")
    return candidate if candidate.is_file() else None


def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _call_hook(hook: InterruptHook | None, stage: str) -> None:
    if hook is not None:
        hook(stage)


def _iter_workspace_files(
    workspace_root: Path,
    *,
    include_dirs: tuple[str, ...],
    exclude_dirs: frozenset[str],
    include_exports: bool,
) -> list[_StagedFile]:
    staged: list[_StagedFile] = []
    dirs = list(include_dirs)
    if include_exports and "export" not in dirs:
        dirs.append("export")

    exclude = set(exclude_dirs)
    if include_exports:
        exclude.discard("export")

    for dirname in dirs:
        if dirname in exclude:
            continue
        root = workspace_root / dirname
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            # Přeskoč symlinky vedoucí mimo (pojistka)
            try:
                path.resolve().relative_to(workspace_root.resolve())
            except ValueError:
                continue
            rel = path.relative_to(workspace_root).as_posix()
            archive_path = normalize_archive_path(f"workspace/{rel}")
            staged.append(
                _StagedFile(
                    source=path,
                    archive_path=archive_path,
                    component=COMPONENT_WORKSPACE,
                    required=True,
                )
            )
    return staged


def _atomic_replace(src: Path, dst: Path) -> None:
    """Atomicky nahradí ``dst`` souborem ``src`` (stejný filesystem)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)


def create_instance_backup(
    target_path: str | Path,
    *,
    workspace_root: Path | None = None,
    database_path: Path | None = None,
    settings_path: Path | None = None,
    include_exports: bool = False,
    include_dirs: tuple[str, ...] | None = None,
    progress_callback: ProgressCallback | None = None,
    interrupt_hook: InterruptHook | None = None,
    verify: bool = True,
) -> CreateInstanceBackupResult:
    """
    Vytvoří úplnou zálohu instance jako ``*.mbbackup``.

    Postup:
    1. Staging dočasného adresáře (DB přes SQLite backup API).
    2. Zápis do ``*.mbbackup.partial``.
    3. Metadata se stavem ``complete`` + ověření.
    4. Atomické ``os.replace`` na cílový ``*.mbbackup``.

    Při chybě se partial/staging smaže a cílový soubor se nevydá za platný.
    """
    target = Path(target_path)
    if target.suffix.lower() != BACKUP_EXTENSION:
        raise InstanceBackupError(
            f"Cíl musí mít příponu {BACKUP_EXTENSION}, dostáno {target.suffix!r}."
        )

    if workspace_root is None or database_path is None:
        from core.services.storage_service import storage_service

        storage_service.ensure_structure()
        workspace_root = workspace_root or storage_service.base
        database_path = database_path or storage_service.database_path

    workspace_root = Path(workspace_root)
    database_path = Path(database_path)

    if not database_path.is_file():
        raise InstanceBackupError(f"Databáze neexistuje: {database_path}")

    include = include_dirs or DEFAULT_WORKSPACE_INCLUDE_DIRS
    settings_file = resolve_settings_file(settings_path)

    partial = target.with_name(target.name + PARTIAL_SUFFIX)
    staging_parent = target.parent
    staging_parent.mkdir(parents=True, exist_ok=True)

    staging_dir: Path | None = None
    created_ok = False

    try:
        _emit(progress_callback, "Připravuji staging…")
        _call_hook(interrupt_hook, "before_staging")
        staging_dir = Path(
            tempfile.mkdtemp(prefix="mbbackup-staging-", dir=str(staging_parent))
        )

        db_dest = staging_dir / "manager_bozp.db"
        _emit(progress_callback, "Vytvářím konzistentní kopii databáze…")
        _call_hook(interrupt_hook, "before_database_snapshot")
        try:
            integrity = create_sqlite_snapshot(database_path, db_dest)
        except SqliteSnapshotError as exc:
            raise InstanceBackupError(str(exc)) from exc

        db_info = inspect_sqlite_file(db_dest)
        integrity = str(db_info["integrity_check"])
        quick_check = str(db_info["quick_check"])
        db_size = int(db_info["size"])  # type: ignore[arg-type]
        db_empty = bool(db_info["empty"])
        schema_version = read_sqlite_user_version(db_dest)

        staged_files: list[_StagedFile] = [
            _StagedFile(
                source=db_dest,
                archive_path=DATABASE_ARCHIVE_NAME,
                component=COMPONENT_DATABASE,
                required=True,
            )
        ]
        staged_files.extend(
            _iter_workspace_files(
                workspace_root,
                include_dirs=include,
                exclude_dirs=DEFAULT_WORKSPACE_EXCLUDE_DIRS,
                include_exports=include_exports,
            )
        )

        if settings_file is not None:
            staged_settings = staging_dir / "settings.json"
            staged_settings.write_bytes(settings_file.read_bytes())
            staged_files.append(
                _StagedFile(
                    source=staged_settings,
                    archive_path="settings/settings.json",
                    component=COMPONENT_SETTINGS,
                    required=False,
                )
            )

        _call_hook(interrupt_hook, "before_hash")
        entries: list[BackupFileEntry] = []
        for item in staged_files:
            digest = sha256_file(item.source)
            size = item.source.stat().st_size
            entries.append(
                build_file_entry(
                    item.archive_path,
                    component=item.component,
                    size=size,
                    sha256=digest,
                    required=item.required,
                )
            )

        metadata = create_backup_metadata(
            files=entries,
            included_components=list(REQUIRED_ARCHIVE_ROOTS),
            package_status=PACKAGE_STATUS_CREATING,
            database_integrity=integrity,
            database_quick_check=quick_check,
            database_size=db_size,
            database_empty=db_empty,
            schema_version=schema_version,
            validate=True,
        )
        metadata = mark_package_complete(metadata)

        if partial.exists():
            partial.unlink()

        _emit(progress_callback, "Zapisuji balíček…")
        _call_hook(interrupt_hook, "before_zip")
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Nejdřív obsah, metadata na konec (jasný complete snapshot).
            for item in staged_files:
                zf.write(item.source, item.archive_path)
            _call_hook(interrupt_hook, "before_metadata_write")
            zf.writestr(
                METADATA_FILENAME,
                metadata.to_json(),
                compress_type=zipfile.ZIP_DEFLATED,
            )

        _call_hook(interrupt_hook, "after_zip")
        _emit(progress_callback, "Ověřuji balíček…")
        if verify:
            try:
                # Partial má příponu ``.mbbackup.partial`` – příponu kontrolujeme až po rename.
                verified_meta = verify_instance_backup_package(
                    partial,
                    require_extension=False,
                )
            except BackupPackageVerificationError as exc:
                raise InstanceBackupError(
                    f"Vytvořený balíček neprošel kontrolou: {exc}"
                ) from exc
            metadata = verified_meta

        _call_hook(interrupt_hook, "before_rename")
        _emit(progress_callback, "Dokončuji atomickým přejmenováním…")
        if target.exists():
            target.unlink()
        _atomic_replace(partial, target)

        if verify:
            try:
                metadata = verify_instance_backup_package(target, require_extension=True)
            except BackupPackageVerificationError as exc:
                target.unlink(missing_ok=True)
                raise InstanceBackupError(
                    f"Finální balíček neprošel kontrolou: {exc}"
                ) from exc

        created_ok = True
        return CreateInstanceBackupResult(
            path=target,
            metadata=metadata,
            verified=verify,
            database_integrity=integrity,
            staging_dir=staging_dir,
            partial_path_used=partial,
        )
    except Exception:
        # Úklid neplatných artefaktů – nikdy nenechat complete cílový soubor
        # z této neúspěšné operace.
        if partial.exists():
            partial.unlink(missing_ok=True)
        raise
    finally:
        if staging_dir is not None and staging_dir.exists():
            _cleanup_tree(staging_dir)
        if not created_ok and partial.exists():
            partial.unlink(missing_ok=True)


def _cleanup_tree(root: Path) -> None:
    import shutil

    shutil.rmtree(root, ignore_errors=True)
