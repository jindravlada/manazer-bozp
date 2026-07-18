"""Bezpečná obnova instance z ``*.mbbackup`` (BACKUP-2a).

Bez UI. Bez rollbacku po úspěšném přepnutí (BACKUP-2b).
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from core.backup.constants import (
    BACKUP_EXTENSION,
    COMPONENT_DATABASE,
    COMPONENT_SETTINGS,
    COMPONENT_WORKSPACE,
    INTEGRITY_INVALID,
    METADATA_FILENAME,
    RESTORE_ERR_BAD_ARCHIVE,
    RESTORE_ERR_DISK_FULL,
    RESTORE_ERR_INTEGRITY,
    RESTORE_ERR_INTERRUPTED,
    RESTORE_ERR_INVALID_DATABASE,
    RESTORE_ERR_INVALID_METADATA,
    RESTORE_ERR_MISSING_COMPONENT,
    RESTORE_ERR_POSTCHECK,
    RESTORE_ERR_UNSAFE_PATH,
    RESTORE_ERR_WRITE_ERROR,
)
from core.backup.package_create import DATABASE_ARCHIVE_NAME
from core.backup.package_extract import SafeExtractError, safe_extract_zip_member
from core.backup.package_integrity import (
    BackupIntegrityReport,
    BackupPackageVerificationError,
    inspect_backup_integrity,
)
from core.backup.paths import BackupPathError, normalize_archive_path
from core.backup.sqlite_snapshot import inspect_sqlite_file, sqlite_integrity_check

ProgressCallback = Callable[[str], None]
InterruptHook = Callable[[str], None]


class InstanceRestoreError(RuntimeError):
    """Chyba obnovy instance s jednoznačným diagnostickým kódem."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"[{code}] {message}")


@dataclass
class RestoreInstanceBackupResult:
    """Výsledek úspěšné obnovy."""

    workspace_root: Path
    database_path: Path
    settings_path: Path | None
    package_path: Path
    integrity: BackupIntegrityReport
    database_integrity: str
    preserved_backups_dir: bool = False
    notes: list[str] = field(default_factory=list)


def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _call_hook(hook: InterruptHook | None, stage: str) -> None:
    if hook is None:
        return
    try:
        hook(stage)
    except InstanceRestoreError:
        raise
    except Exception as exc:  # noqa: BLE001 – testovací / vnější přerušení
        raise InstanceRestoreError(
            RESTORE_ERR_INTERRUPTED,
            f"Obnova přerušena ve fázi {stage}: {exc}",
        ) from exc


def _map_integrity_failure(report: BackupIntegrityReport) -> InstanceRestoreError:
    codes = {issue.code for issue in report.errors}
    if "bad_zip" in codes or "bad_extension" in codes:
        return InstanceRestoreError(
            RESTORE_ERR_BAD_ARCHIVE,
            "; ".join(i.message for i in report.errors) or "Poškozený archiv.",
        )
    if any(
        c.startswith("database_") or c in {"missing_database", "missing_database_dir"}
        for c in codes
    ):
        return InstanceRestoreError(
            RESTORE_ERR_INVALID_DATABASE,
            "; ".join(i.message for i in report.errors) or "Neplatná databáze v balíčku.",
        )
    if any(
        c in {
            "missing_metadata",
            "invalid_metadata",
            "invalid_metadata_json",
            "unsupported_format_version",
            "bad_format_version",
            "bad_package_kind",
            "incomplete_package",
        }
        for c in codes
    ):
        return InstanceRestoreError(
            RESTORE_ERR_INVALID_METADATA,
            "; ".join(i.message for i in report.errors) or "Neplatná metadata.",
        )
    if any(c in {"missing_file", "missing_archive_root", "missing_component"} for c in codes):
        return InstanceRestoreError(
            RESTORE_ERR_MISSING_COMPONENT,
            "; ".join(i.message for i in report.errors) or "Chybějící komponenta.",
        )
    return InstanceRestoreError(
        RESTORE_ERR_INTEGRITY,
        "; ".join(i.message for i in report.errors) or "Balíček neprošel kontrolou integrity.",
    )


def _estimate_needed_bytes(package_path: Path, content_size: int) -> int:
    # extract + new workspace (+ rezerva)
    package_size = package_path.stat().st_size
    base = max(content_size, package_size)
    return int(base * 2.5) + 16 * 1024 * 1024


def _ensure_free_space(target_dir: Path, needed: int) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(target_dir)
    if usage.free < needed:
        raise InstanceRestoreError(
            RESTORE_ERR_DISK_FULL,
            f"Nedostatek místa na disku: potřeba cca {needed} B, volných {usage.free} B.",
        )


def _cleanup_tree(path: Path | None) -> None:
    if path is None:
        return
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _atomic_replace_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".mbrestore-tmp")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(source, tmp)
    os.replace(tmp, destination)


def _build_workspace_from_extract(
    extract_root: Path,
    new_workspace: Path,
    *,
    old_workspace: Path | None,
) -> bool:
    """
    Sestaví nový workspace z rozbaleného balíčku.

    Returns:
        True pokud byla zachována složka ``zalohy`` z původního workspace.
    """
    new_workspace.mkdir(parents=True, exist_ok=False)

    db_src = extract_root / "database" / "manager_bozp.db"
    if not db_src.is_file():
        # fallback na DATABASE_ARCHIVE_NAME layout
        alt = extract_root / Path(*DATABASE_ARCHIVE_NAME.split("/"))
        if alt.is_file():
            db_src = alt
        else:
            raise InstanceRestoreError(
                RESTORE_ERR_MISSING_COMPONENT,
                "V rozbaleném balíčku chybí database/manager_bozp.db.",
            )

    db_dest_dir = new_workspace / "databaze"
    db_dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_src, db_dest_dir / "manager_bozp.db")

    workspace_src = extract_root / COMPONENT_WORKSPACE
    if workspace_src.is_dir():
        for item in workspace_src.iterdir():
            dest = new_workspace / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            elif item.is_file():
                shutil.copy2(item, dest)

    preserved = False
    if old_workspace is not None:
        old_zalohy = old_workspace / "zalohy"
        if old_zalohy.exists():
            shutil.copytree(old_zalohy, new_workspace / "zalohy")
            preserved = True

    for dirname in ("import", "logy", "export", "zalohy"):
        (new_workspace / dirname).mkdir(parents=True, exist_ok=True)

    return preserved


def _verify_prepared_workspace(new_workspace: Path) -> str:
    db_path = new_workspace / "databaze" / "manager_bozp.db"
    if not db_path.is_file():
        raise InstanceRestoreError(
            RESTORE_ERR_MISSING_COMPONENT,
            "Připravená instance neobsahuje databázi.",
        )
    try:
        integrity = sqlite_integrity_check(db_path)
    except Exception as exc:  # noqa: BLE001
        raise InstanceRestoreError(
            RESTORE_ERR_INVALID_DATABASE,
            f"Databázi v připravené instanci nelze ověřit: {exc}",
        ) from exc
    if integrity != "ok":
        raise InstanceRestoreError(
            RESTORE_ERR_INVALID_DATABASE,
            f"integrity_check připravené DB selhal: {integrity}",
        )

    # Povinné workspace podsložky (mohou být prázdné, ale DB musí existovat)
    if not (new_workspace / "databaze").is_dir():
        raise InstanceRestoreError(
            RESTORE_ERR_MISSING_COMPONENT,
            "Chybí adresář databaze/ v připravené instanci.",
        )
    return integrity


def _verify_live_workspace(
    workspace_root: Path,
    *,
    expected_db_size: int | None,
) -> str:
    db_path = workspace_root / "databaze" / "manager_bozp.db"
    if not db_path.is_file():
        raise InstanceRestoreError(
            RESTORE_ERR_POSTCHECK,
            "Po obnově neexistuje databáze.",
        )
    info = inspect_sqlite_file(db_path)
    integrity = str(info["integrity_check"])
    if integrity != "ok":
        raise InstanceRestoreError(
            RESTORE_ERR_POSTCHECK,
            f"Po obnově integrity_check != ok: {integrity}",
        )
    if expected_db_size is not None and int(info["size"]) != expected_db_size:  # type: ignore[arg-type]
        raise InstanceRestoreError(
            RESTORE_ERR_POSTCHECK,
            "Po obnově velikost DB neodpovídá metadatum balíčku.",
        )
    if not (workspace_root / "databaze").is_dir():
        raise InstanceRestoreError(
            RESTORE_ERR_POSTCHECK,
            "Po obnově chybí povinná komponenta databaze/.",
        )
    return integrity


def _atomic_swap_directories(current: Path, new_dir: Path, previous_dir: Path) -> None:
    """
    Atomicky (v rámci rename) vymění ``current`` za ``new_dir``.

    Původní ``current`` přesune do ``previous_dir``. Při selhání druhého rename
    se pokusí vrátit ``previous_dir`` zpět na ``current`` (best-effort, ne 2b).
    """
    parent = current.parent
    parent.mkdir(parents=True, exist_ok=True)

    if previous_dir.exists():
        raise InstanceRestoreError(
            RESTORE_ERR_WRITE_ERROR,
            f"Dočasný adresář pro původní data už existuje: {previous_dir}",
        )
    if not new_dir.exists():
        raise InstanceRestoreError(
            RESTORE_ERR_WRITE_ERROR,
            f"Nová instance neexistuje: {new_dir}",
        )

    swapped_away = False
    try:
        if current.exists():
            os.rename(current, previous_dir)
            swapped_away = True
        os.rename(new_dir, current)
    except OSError as exc:
        if swapped_away and previous_dir.exists() and not current.exists():
            try:
                os.rename(previous_dir, current)
            except OSError:
                pass
        raise InstanceRestoreError(
            RESTORE_ERR_WRITE_ERROR,
            f"Atomická výměna workspace selhala: {exc}",
        ) from exc


def restore_instance_backup(
    package_path: str | Path,
    *,
    workspace_root: Path | None = None,
    settings_path: Path | None = None,
    progress_callback: ProgressCallback | None = None,
    interrupt_hook: InterruptHook | None = None,
    keep_previous: bool = False,
) -> RestoreInstanceBackupResult:
    """
    Obnoví celou instance z ``*.mbbackup``.

    Postup:
    1. otevření + kontrola integrity (BACKUP-1c),
    2. rozbalení do temp (bez ``extractall``),
    3. sestavení nové instance vedle současné,
    4. atomická výměna workspace,
    5. obnova settings (atomický zápis),
    6. post-check + úklid.

    Při chybě před výměnou zůstává původní workspace beze změny.
    """
    package = Path(package_path)
    if package.suffix.lower() != BACKUP_EXTENSION:
        raise InstanceRestoreError(
            RESTORE_ERR_BAD_ARCHIVE,
            f"Očekávána přípona {BACKUP_EXTENSION}, dostáno {package.suffix!r}.",
        )
    if not package.is_file():
        raise InstanceRestoreError(
            RESTORE_ERR_BAD_ARCHIVE,
            f"Soubor zálohy neexistuje: {package}",
        )

    if workspace_root is None:
        from core.services.storage_service import storage_service

        storage_service.ensure_structure()
        workspace_root = storage_service.base

    workspace_root = Path(workspace_root)

    if settings_path is None:
        try:
            from core.settings.settings_manager import settings as settings_manager

            settings_path = Path(settings_manager.file)
        except Exception:
            settings_path = Path("data/nastaveni/settings.json")
    else:
        settings_path = Path(settings_path)

    extract_dir: Path | None = None
    new_workspace: Path | None = None
    previous_workspace: Path | None = None
    swap_done = False
    notes: list[str] = []

    try:
        _emit(progress_callback, "Kontroluji integritu balíčku…")
        _call_hook(interrupt_hook, "before_integrity")
        report = inspect_backup_integrity(package)
        if report.status == INTEGRITY_INVALID:
            raise _map_integrity_failure(report)

        if report.metadata is None:
            raise InstanceRestoreError(
                RESTORE_ERR_INVALID_METADATA,
                "Balíček neobsahuje použitelná metadata.",
            )
        metadata = report.metadata

        content_size = metadata.total_content_size or package.stat().st_size
        needed = _estimate_needed_bytes(package, content_size)
        _ensure_free_space(workspace_root.parent, needed)

        token = uuid.uuid4().hex[:10]
        parent = workspace_root.parent
        extract_dir = Path(
            tempfile.mkdtemp(prefix=f"mbrestore-extract-{token}-", dir=str(parent))
        )
        new_workspace = parent / f".{workspace_root.name}.mbrestore-new-{token}"
        previous_workspace = parent / f".{workspace_root.name}.mbrestore-prev-{token}"

        _emit(progress_callback, "Rozbaluji balíček do dočasného adresáře…")
        _call_hook(interrupt_hook, "before_extract")
        try:
            with zipfile.ZipFile(package, "r") as zf:
                # metadata + všechny soubory z manifestu
                members = [METADATA_FILENAME]
                for entry in metadata.files:
                    try:
                        members.append(normalize_archive_path(entry.path))
                    except BackupPathError as exc:
                        raise InstanceRestoreError(
                            RESTORE_ERR_UNSAFE_PATH, str(exc)
                        ) from exc
                # unikátní zachování pořadí
                seen: set[str] = set()
                ordered: list[str] = []
                for name in members:
                    if name not in seen:
                        seen.add(name)
                        ordered.append(name)

                for name in ordered:
                    try:
                        safe_extract_zip_member(zf, name, extract_dir)
                    except SafeExtractError as exc:
                        msg = str(exc)
                        if "Absolutní" in msg or ".." in msg or "uniká" in msg:
                            raise InstanceRestoreError(
                                RESTORE_ERR_UNSAFE_PATH, msg
                            ) from exc
                        raise InstanceRestoreError(
                            RESTORE_ERR_WRITE_ERROR, msg
                        ) from exc
        except zipfile.BadZipFile as exc:
            raise InstanceRestoreError(
                RESTORE_ERR_BAD_ARCHIVE, f"Poškozený archiv: {exc}"
            ) from exc

        _call_hook(interrupt_hook, "after_extract")

        # Ověření povinných komponent v extract
        db_file = extract_dir / "database" / "manager_bozp.db"
        if not db_file.is_file():
            raise InstanceRestoreError(
                RESTORE_ERR_MISSING_COMPONENT,
                "Po rozbalení chybí database/manager_bozp.db.",
            )
        if not (extract_dir / COMPONENT_WORKSPACE).exists():
            # workspace může být prázdný adresář – vytvoř placeholder kontrolou metadata
            if COMPONENT_WORKSPACE not in metadata.included_components:
                raise InstanceRestoreError(
                    RESTORE_ERR_MISSING_COMPONENT,
                    "Balíček neobsahuje komponentu workspace.",
                )
            (extract_dir / COMPONENT_WORKSPACE).mkdir(parents=True, exist_ok=True)
        if COMPONENT_SETTINGS not in metadata.included_components:
            raise InstanceRestoreError(
                RESTORE_ERR_MISSING_COMPONENT,
                "Balíček neobsahuje komponentu settings.",
            )
        if COMPONENT_DATABASE not in metadata.included_components:
            raise InstanceRestoreError(
                RESTORE_ERR_MISSING_COMPONENT,
                "Balíček neobsahuje komponentu database.",
            )

        _emit(progress_callback, "Připravuji novou instance dat…")
        _call_hook(interrupt_hook, "before_prepare")
        try:
            if new_workspace.exists():
                _cleanup_tree(new_workspace)
            preserved = _build_workspace_from_extract(
                extract_dir,
                new_workspace,
                old_workspace=workspace_root if workspace_root.exists() else None,
            )
        except InstanceRestoreError:
            raise
        except OSError as exc:
            raise InstanceRestoreError(
                RESTORE_ERR_WRITE_ERROR,
                f"Příprava nové instance selhala: {exc}",
            ) from exc

        prepared_integrity = _verify_prepared_workspace(new_workspace)
        _call_hook(interrupt_hook, "after_prepare")

        # Přerušení před výměnou = původní data nedotčená
        _call_hook(interrupt_hook, "before_swap")
        _emit(progress_callback, "Provádím atomickou výměnu dat…")
        _atomic_swap_directories(workspace_root, new_workspace, previous_workspace)
        swap_done = True
        new_workspace = None  # už je workspace_root

        # Settings – až po úspěšném swap workspace (workspace je kritický)
        settings_src = extract_dir / COMPONENT_SETTINGS / "settings.json"
        restored_settings: Path | None = None
        if settings_src.is_file():
            try:
                _atomic_replace_file(settings_src, settings_path)
                restored_settings = settings_path
            except OSError as exc:
                notes.append(
                    f"Workspace obnoven, ale settings se nepodařilo zapsat: {exc}"
                )
        else:
            notes.append("Balíček neobsahoval settings/settings.json – UI nastavení beze změny.")

        _call_hook(interrupt_hook, "after_swap")
        _emit(progress_callback, "Ověřuji obnovenou instance…")
        live_integrity = _verify_live_workspace(
            workspace_root,
            expected_db_size=metadata.database_size,
        )

        # Úklid předchozí instance
        if previous_workspace is not None and previous_workspace.exists():
            if keep_previous:
                notes.append(f"Původní data ponechána v {previous_workspace}")
            else:
                _cleanup_tree(previous_workspace)
                previous_workspace = None

        _cleanup_tree(extract_dir)
        extract_dir = None

        _call_hook(interrupt_hook, "after_cleanup")
        return RestoreInstanceBackupResult(
            workspace_root=workspace_root,
            database_path=workspace_root / "databaze" / "manager_bozp.db",
            settings_path=restored_settings,
            package_path=package,
            integrity=report,
            database_integrity=live_integrity or prepared_integrity,
            preserved_backups_dir=preserved,
            notes=notes,
        )
    except InstanceRestoreError:
        raise
    except BackupPackageVerificationError as exc:
        raise InstanceRestoreError(RESTORE_ERR_INTEGRITY, str(exc)) from exc
    except InterruptedError as exc:
        raise InstanceRestoreError(RESTORE_ERR_INTERRUPTED, str(exc) or "Obnova přerušena.") from exc
    except OSError as exc:
        err = getattr(exc, "errno", None)
        if err in {28, 112}:  # ENOSPC / Windows disk full-ish
            raise InstanceRestoreError(
                RESTORE_ERR_DISK_FULL, f"Nedostatek místa / chyba disku: {exc}"
            ) from exc
        raise InstanceRestoreError(
            RESTORE_ERR_WRITE_ERROR, f"Chyba zápisu při obnově: {exc}"
        ) from exc
    finally:
        # Při chybě před swapy uklidíme temporary artefakty; po swapy
        # new_workspace je None / už přejmenovaný.
        if not swap_done:
            _cleanup_tree(new_workspace)
            _cleanup_tree(extract_dir)
            # previous by neměl existovat, pokud swap neproběhl
            if previous_workspace is not None and previous_workspace.exists():
                # pokud somehow zůstal, vrať (safety)
                if not workspace_root.exists():
                    try:
                        os.rename(previous_workspace, workspace_root)
                    except OSError:
                        pass
                else:
                    _cleanup_tree(previous_workspace)
        else:
            _cleanup_tree(extract_dir)
