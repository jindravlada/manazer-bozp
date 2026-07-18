"""Bezpečná obnova instance z ``*.mbbackup`` (BACKUP-2a + rollback BACKUP-2b).

Bez UI. Automatická kontrola recovery markeru při startu = pozdější fáze.
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
    RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK,
    RESTORE_ERR_FAILED_BEFORE_SWAP,
    RESTORE_ERR_INTEGRITY,
    RESTORE_ERR_INTERRUPTED,
    RESTORE_ERR_INVALID_DATABASE,
    RESTORE_ERR_INVALID_METADATA,
    RESTORE_ERR_MISSING_COMPONENT,
    RESTORE_ERR_POSTCHECK,
    RESTORE_ERR_ROLLBACK_FAILED,
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
from core.backup.recovery_marker import (
    build_recovery_marker_payload,
    recovery_marker_path,
    remove_recovery_marker,
    update_recovery_marker_phase,
    utc_now_iso,
    write_recovery_marker,
)
from core.backup.sqlite_snapshot import inspect_sqlite_file, sqlite_integrity_check

ProgressCallback = Callable[[str], None]
InterruptHook = Callable[[str], None]

# Specifické kódy, které samy o sobě už popisují stav před swapy.
_BEFORE_SWAP_CODES = frozenset(
    {
        RESTORE_ERR_BAD_ARCHIVE,
        RESTORE_ERR_INVALID_METADATA,
        RESTORE_ERR_INVALID_DATABASE,
        RESTORE_ERR_MISSING_COMPONENT,
        RESTORE_ERR_DISK_FULL,
        RESTORE_ERR_WRITE_ERROR,
        RESTORE_ERR_INTERRUPTED,
        RESTORE_ERR_INTEGRITY,
        RESTORE_ERR_UNSAFE_PATH,
        RESTORE_ERR_FAILED_BEFORE_SWAP,
    }
)


class InstanceRestoreError(RuntimeError):
    """Chyba obnovy instance s jednoznačným diagnostickým kódem."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        phase: str | None = None,
        rolled_back: bool = False,
        cause_code: str | None = None,
        marker_path: str | Path | None = None,
        preserved_paths: list[str] | None = None,
    ):
        self.code = code
        self.phase = phase
        self.rolled_back = rolled_back
        self.cause_code = cause_code
        self.marker_path = str(marker_path) if marker_path else None
        self.preserved_paths = list(preserved_paths or ())
        detail = f"[{code}] {message}"
        if rolled_back:
            detail += " Původní data byla obnovena rollbackem."
        super().__init__(detail)


@dataclass
class RestoreInstanceBackupResult:
    """Výsledek úspěšné obnovy (zpětně kompatibilní s BACKUP-2a)."""

    workspace_root: Path
    database_path: Path
    settings_path: Path | None
    package_path: Path
    integrity: BackupIntegrityReport
    database_integrity: str
    preserved_backups_dir: bool = False
    notes: list[str] = field(default_factory=list)
    # BACKUP-2b
    restored: bool = True
    post_check_ok: bool = True
    rollback_copy_removed: bool = True
    warnings: list[str] = field(default_factory=list)
    recovery_marker_removed: bool = True


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
            phase=stage,
        ) from exc


def _map_integrity_failure(report: BackupIntegrityReport) -> InstanceRestoreError:
    codes = {issue.code for issue in report.errors}
    if "bad_zip" in codes or "bad_extension" in codes:
        return InstanceRestoreError(
            RESTORE_ERR_BAD_ARCHIVE,
            "; ".join(i.message for i in report.errors) or "Poškozený archiv.",
            phase="integrity",
        )
    if any(
        c.startswith("database_") or c in {"missing_database", "missing_database_dir"}
        for c in codes
    ):
        return InstanceRestoreError(
            RESTORE_ERR_INVALID_DATABASE,
            "; ".join(i.message for i in report.errors) or "Neplatná databáze v balíčku.",
            phase="integrity",
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
            phase="integrity",
        )
    if any(c in {"missing_file", "missing_archive_root", "missing_component"} for c in codes):
        return InstanceRestoreError(
            RESTORE_ERR_MISSING_COMPONENT,
            "; ".join(i.message for i in report.errors) or "Chybějící komponenta.",
            phase="integrity",
        )
    return InstanceRestoreError(
        RESTORE_ERR_INTEGRITY,
        "; ".join(i.message for i in report.errors) or "Balíček neprošel kontrolou integrity.",
        phase="integrity",
    )


def _as_before_swap_error(exc: InstanceRestoreError) -> InstanceRestoreError:
    if exc.code in {
        RESTORE_ERR_FAILED_BEFORE_SWAP,
        RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK,
        RESTORE_ERR_ROLLBACK_FAILED,
    }:
        return exc
    if exc.code in _BEFORE_SWAP_CODES:
        return InstanceRestoreError(
            RESTORE_ERR_FAILED_BEFORE_SWAP,
            str(exc).removeprefix(f"[{exc.code}] ").strip() or exc.code,
            phase=exc.phase or "before_swap",
            cause_code=exc.code,
            marker_path=exc.marker_path,
            preserved_paths=exc.preserved_paths,
        )
    return InstanceRestoreError(
        RESTORE_ERR_FAILED_BEFORE_SWAP,
        str(exc),
        phase=exc.phase or "before_swap",
        cause_code=exc.code,
        marker_path=exc.marker_path,
        preserved_paths=exc.preserved_paths,
    )


def _estimate_needed_bytes(package_path: Path, content_size: int) -> int:
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
            phase="preflight",
        )


def _cleanup_tree(path: Path | None) -> bool:
    """Smaže strom. Vrací True při úspěchu / neexistenci, False při chybě."""
    if path is None:
        return True
    if not path.exists():
        return True
    try:
        shutil.rmtree(path)
        return True
    except OSError:
        return False


def _atomic_replace_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".mbrestore-tmp")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(source, tmp)
    os.replace(tmp, destination)


def _backup_settings_file(settings_path: Path) -> Path | None:
    """Zálohuje existující settings vedle souboru; vrací cestu k záloze."""
    if not settings_path.is_file():
        return None
    backup = settings_path.with_name(settings_path.name + ".mbrestore-bak")
    if backup.exists():
        backup.unlink()
    shutil.copy2(settings_path, backup)
    return backup


def _restore_settings_backup(settings_path: Path, settings_backup: Path | None) -> None:
    if settings_backup is None:
        # Původní settings neexistovaly – odstraň případně zapsané nové.
        if settings_path.exists():
            settings_path.unlink(missing_ok=True)
        return
    if not settings_backup.is_file():
        raise InstanceRestoreError(
            RESTORE_ERR_ROLLBACK_FAILED,
            f"Záloha settings pro rollback chybí: {settings_backup}",
            phase="rollback_settings",
        )
    _atomic_replace_file(settings_backup, settings_path)


def _build_workspace_from_extract(
    extract_root: Path,
    new_workspace: Path,
    *,
    old_workspace: Path | None,
) -> bool:
    new_workspace.mkdir(parents=True, exist_ok=False)

    db_src = extract_root / "database" / "manager_bozp.db"
    if not db_src.is_file():
        alt = extract_root / Path(*DATABASE_ARCHIVE_NAME.split("/"))
        if alt.is_file():
            db_src = alt
        else:
            raise InstanceRestoreError(
                RESTORE_ERR_MISSING_COMPONENT,
                "V rozbaleném balíčku chybí database/manager_bozp.db.",
                phase="prepare",
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
            phase="prepare",
        )
    try:
        integrity = sqlite_integrity_check(db_path)
    except Exception as exc:  # noqa: BLE001
        raise InstanceRestoreError(
            RESTORE_ERR_INVALID_DATABASE,
            f"Databázi v připravené instanci nelze ověřit: {exc}",
            phase="prepare",
        ) from exc
    if integrity != "ok":
        raise InstanceRestoreError(
            RESTORE_ERR_INVALID_DATABASE,
            f"integrity_check připravené DB selhal: {integrity}",
            phase="prepare",
        )
    if not (new_workspace / "databaze").is_dir():
        raise InstanceRestoreError(
            RESTORE_ERR_MISSING_COMPONENT,
            "Chybí adresář databaze/ v připravené instanci.",
            phase="prepare",
        )
    return integrity


def _verify_live_workspace(
    workspace_root: Path,
    *,
    expected_db_size: int | None,
    phase: str = "post_check",
) -> str:
    db_path = workspace_root / "databaze" / "manager_bozp.db"
    if not db_path.is_file():
        raise InstanceRestoreError(
            RESTORE_ERR_POSTCHECK,
            "Po obnově neexistuje databáze.",
            phase=phase,
        )
    info = inspect_sqlite_file(db_path)
    integrity = str(info["integrity_check"])
    if integrity != "ok":
        raise InstanceRestoreError(
            RESTORE_ERR_POSTCHECK,
            f"Po obnově integrity_check != ok: {integrity}",
            phase=phase,
        )
    if expected_db_size is not None and int(info["size"]) != expected_db_size:  # type: ignore[arg-type]
        raise InstanceRestoreError(
            RESTORE_ERR_POSTCHECK,
            "Po obnově velikost DB neodpovídá metadatum balíčku.",
            phase=phase,
        )
    if not (workspace_root / "databaze").is_dir():
        raise InstanceRestoreError(
            RESTORE_ERR_POSTCHECK,
            "Po obnově chybí povinná komponenta databaze/.",
            phase=phase,
        )
    return integrity


def _atomic_swap_directories(current: Path, new_dir: Path, previous_dir: Path) -> None:
    """Přesune ``current`` → ``previous_dir`` a ``new_dir`` → ``current``."""
    parent = current.parent
    parent.mkdir(parents=True, exist_ok=True)

    if previous_dir.exists():
        raise InstanceRestoreError(
            RESTORE_ERR_WRITE_ERROR,
            f"Dočasný adresář pro původní data už existuje: {previous_dir}",
            phase="swap",
        )
    if not new_dir.exists():
        raise InstanceRestoreError(
            RESTORE_ERR_WRITE_ERROR,
            f"Nová instance neexistuje: {new_dir}",
            phase="swap",
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
            phase="swap",
        ) from exc


def _perform_rollback(
    *,
    workspace_root: Path,
    rollback_workspace: Path,
    failed_workspace: Path,
    settings_path: Path,
    settings_backup: Path | None,
    marker_file: Path | None,
    interrupt_hook: InterruptHook | None,
) -> None:
    """
    Vrátí původní workspace + settings. Při selhání nic automaticky nemaže.
    """
    if marker_file is not None and marker_file.exists():
        update_recovery_marker_phase(marker_file, "rolling_back")

    preserved: list[str] = []
    try:
        _call_hook(interrupt_hook, "during_rollback")

        # Odstav neúspěšně obnovená data
        if workspace_root.exists():
            if failed_workspace.exists():
                raise InstanceRestoreError(
                    RESTORE_ERR_ROLLBACK_FAILED,
                    f"Cíl pro odstavení neúspěšné obnovy už existuje: {failed_workspace}",
                    phase="rolling_back",
                    marker_path=marker_file,
                    preserved_paths=[
                        str(workspace_root),
                        str(rollback_workspace),
                        str(failed_workspace),
                    ],
                )
            os.rename(workspace_root, failed_workspace)
            preserved.append(str(failed_workspace))

        if not rollback_workspace.exists():
            raise InstanceRestoreError(
                RESTORE_ERR_ROLLBACK_FAILED,
                f"Rollback kopie neexistuje: {rollback_workspace}",
                phase="rolling_back",
                marker_path=marker_file,
                preserved_paths=preserved + [str(workspace_root)],
            )

        os.rename(rollback_workspace, workspace_root)
        _restore_settings_backup(settings_path, settings_backup)

        # Ověř původní DB
        db_path = workspace_root / "databaze" / "manager_bozp.db"
        if not db_path.is_file():
            raise InstanceRestoreError(
                RESTORE_ERR_ROLLBACK_FAILED,
                "Po rollbacku chybí původní databáze.",
                phase="rolling_back",
                marker_path=marker_file,
                preserved_paths=preserved + [str(workspace_root)],
            )
        integrity = sqlite_integrity_check(db_path)
        if integrity != "ok":
            raise InstanceRestoreError(
                RESTORE_ERR_ROLLBACK_FAILED,
                f"Po rollbacku integrity_check původní DB selhal: {integrity}",
                phase="rolling_back",
                marker_path=marker_file,
                preserved_paths=preserved + [str(workspace_root)],
            )

        # Úklid neúspěšné obnovy (best-effort)
        _cleanup_tree(failed_workspace)
        if settings_backup is not None:
            settings_backup.unlink(missing_ok=True)

        if marker_file is not None:
            remove_recovery_marker(marker_file)

        _call_hook(interrupt_hook, "after_rollback")
    except InstanceRestoreError as exc:
        if exc.code == RESTORE_ERR_ROLLBACK_FAILED:
            # Zachovej vše, včetně markeru
            paths = list(exc.preserved_paths)
            for candidate in (
                workspace_root,
                rollback_workspace,
                failed_workspace,
                settings_backup,
                marker_file,
            ):
                if candidate is not None and Path(candidate).exists():
                    paths.append(str(candidate))
            raise InstanceRestoreError(
                RESTORE_ERR_ROLLBACK_FAILED,
                str(exc).removeprefix(f"[{exc.code}] ").strip(),
                phase="rolling_back",
                marker_path=marker_file,
                preserved_paths=sorted(set(paths)),
            ) from exc
        # Přerušení během rollbacku = kritický stav
        paths = []
        for candidate in (
            workspace_root,
            rollback_workspace,
            failed_workspace,
            settings_backup,
            marker_file,
        ):
            if candidate is not None and Path(candidate).exists():
                paths.append(str(candidate))
        raise InstanceRestoreError(
            RESTORE_ERR_ROLLBACK_FAILED,
            f"Rollback přerušen/selhal: {exc}",
            phase="rolling_back",
            cause_code=exc.code,
            marker_path=marker_file,
            preserved_paths=sorted(set(paths)),
        ) from exc
    except OSError as exc:
        paths = []
        for candidate in (
            workspace_root,
            rollback_workspace,
            failed_workspace,
            settings_backup,
            marker_file,
        ):
            if candidate is not None and Path(candidate).exists():
                paths.append(str(candidate))
        raise InstanceRestoreError(
            RESTORE_ERR_ROLLBACK_FAILED,
            f"Rollback selhal: {exc}",
            phase="rolling_back",
            marker_path=marker_file,
            preserved_paths=sorted(set(paths)),
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

    Po atomickém přepnutí při chybě provede automatický rollback původního
    workspace i settings (BACKUP-2b).
    """
    package = Path(package_path)
    if package.suffix.lower() != BACKUP_EXTENSION:
        raise InstanceRestoreError(
            RESTORE_ERR_FAILED_BEFORE_SWAP,
            f"Očekávána přípona {BACKUP_EXTENSION}, dostáno {package.suffix!r}.",
            phase="open",
            cause_code=RESTORE_ERR_BAD_ARCHIVE,
        )
    if not package.is_file():
        raise InstanceRestoreError(
            RESTORE_ERR_FAILED_BEFORE_SWAP,
            f"Soubor zálohy neexistuje: {package}",
            phase="open",
            cause_code=RESTORE_ERR_BAD_ARCHIVE,
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
    rollback_workspace: Path | None = None
    marker_file: Path | None = None
    settings_backup: Path | None = None
    swap_done = False
    notes: list[str] = []
    warnings: list[str] = []
    token = uuid.uuid4().hex[:10]
    started_at = utc_now_iso()
    parent = workspace_root.parent

    try:
        _emit(progress_callback, "Kontroluji integritu balíčku…")
        _call_hook(interrupt_hook, "before_integrity")
        report = inspect_backup_integrity(package)
        if report.status == INTEGRITY_INVALID:
            raise _as_before_swap_error(_map_integrity_failure(report))

        if report.metadata is None:
            raise InstanceRestoreError(
                RESTORE_ERR_FAILED_BEFORE_SWAP,
                "Balíček neobsahuje použitelná metadata.",
                phase="integrity",
                cause_code=RESTORE_ERR_INVALID_METADATA,
            )
        metadata = report.metadata

        content_size = metadata.total_content_size or package.stat().st_size
        needed = _estimate_needed_bytes(package, content_size)
        try:
            _ensure_free_space(parent, needed)
        except InstanceRestoreError as exc:
            raise _as_before_swap_error(exc) from exc

        extract_dir = Path(
            tempfile.mkdtemp(prefix=f"mbrestore-extract-{token}-", dir=str(parent))
        )
        new_workspace = parent / f".{workspace_root.name}.mbrestore-new-{token}"
        rollback_workspace = parent / f".{workspace_root.name}.mbrestore-prev-{token}"
        failed_workspace = parent / f".{workspace_root.name}.mbrestore-failed-{token}"
        marker_file = recovery_marker_path(parent, token)

        write_recovery_marker(
            marker_file,
            build_recovery_marker_payload(
                phase="starting",
                started_at=started_at,
                backup_format_version=metadata.format_version,
                package_path=package,
                workspace_root=workspace_root,
                new_workspace=new_workspace,
                rollback_workspace=rollback_workspace,
                settings_path=settings_path,
                extract_dir=extract_dir,
                token=token,
            ),
        )

        _emit(progress_callback, "Rozbaluji balíček do dočasného adresáře…")
        update_recovery_marker_phase(marker_file, "extracting")
        _call_hook(interrupt_hook, "before_extract")
        try:
            with zipfile.ZipFile(package, "r") as zf:
                members = [METADATA_FILENAME]
                for entry in metadata.files:
                    try:
                        members.append(normalize_archive_path(entry.path))
                    except BackupPathError as exc:
                        raise InstanceRestoreError(
                            RESTORE_ERR_UNSAFE_PATH, str(exc), phase="extract"
                        ) from exc
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
                                RESTORE_ERR_UNSAFE_PATH, msg, phase="extract"
                            ) from exc
                        raise InstanceRestoreError(
                            RESTORE_ERR_WRITE_ERROR, msg, phase="extract"
                        ) from exc
        except zipfile.BadZipFile as exc:
            raise InstanceRestoreError(
                RESTORE_ERR_BAD_ARCHIVE, f"Poškozený archiv: {exc}", phase="extract"
            ) from exc

        _call_hook(interrupt_hook, "after_extract")

        db_file = extract_dir / "database" / "manager_bozp.db"
        if not db_file.is_file():
            raise InstanceRestoreError(
                RESTORE_ERR_MISSING_COMPONENT,
                "Po rozbalení chybí database/manager_bozp.db.",
                phase="extract",
            )
        if not (extract_dir / COMPONENT_WORKSPACE).exists():
            if COMPONENT_WORKSPACE not in metadata.included_components:
                raise InstanceRestoreError(
                    RESTORE_ERR_MISSING_COMPONENT,
                    "Balíček neobsahuje komponentu workspace.",
                    phase="extract",
                )
            (extract_dir / COMPONENT_WORKSPACE).mkdir(parents=True, exist_ok=True)
        if COMPONENT_SETTINGS not in metadata.included_components:
            raise InstanceRestoreError(
                RESTORE_ERR_MISSING_COMPONENT,
                "Balíček neobsahuje komponentu settings.",
                phase="extract",
            )
        if COMPONENT_DATABASE not in metadata.included_components:
            raise InstanceRestoreError(
                RESTORE_ERR_MISSING_COMPONENT,
                "Balíček neobsahuje komponentu database.",
                phase="extract",
            )

        _emit(progress_callback, "Připravuji novou instance dat…")
        update_recovery_marker_phase(marker_file, "preparing")
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
                phase="prepare",
            ) from exc

        prepared_integrity = _verify_prepared_workspace(new_workspace)
        _call_hook(interrupt_hook, "after_prepare")

        # Záloha settings před swapy (součást transakce)
        try:
            settings_backup = _backup_settings_file(settings_path)
        except OSError as exc:
            raise InstanceRestoreError(
                RESTORE_ERR_WRITE_ERROR,
                f"Nelze zálohovat settings před obnovou: {exc}",
                phase="settings_backup",
            ) from exc
        if marker_file.exists():
            update_recovery_marker_phase(
                marker_file,
                "before_swap",
                settings_backup=settings_backup,
            )

        _call_hook(interrupt_hook, "before_swap")
        _emit(progress_callback, "Provádím atomickou výměnu dat…")
        update_recovery_marker_phase(marker_file, "swapping")
        _atomic_swap_directories(workspace_root, new_workspace, rollback_workspace)
        swap_done = True
        new_workspace = None  # už je workspace_root
        update_recovery_marker_phase(marker_file, "after_swap")
        _call_hook(interrupt_hook, "after_swap")

        # Settings – součást transakce; selhání ⇒ rollback
        _emit(progress_callback, "Obnovuji settings…")
        update_recovery_marker_phase(marker_file, "restoring_settings")
        _call_hook(interrupt_hook, "before_settings")
        settings_src = extract_dir / COMPONENT_SETTINGS / "settings.json"
        restored_settings: Path | None = None
        if settings_src.is_file():
            try:
                _atomic_replace_file(settings_src, settings_path)
                restored_settings = settings_path
            except OSError as exc:
                raise InstanceRestoreError(
                    RESTORE_ERR_WRITE_ERROR,
                    f"Obnova settings selhala: {exc}",
                    phase="settings",
                ) from exc
        else:
            notes.append(
                "Balíček neobsahoval settings/settings.json – UI nastavení beze změny."
            )
        _call_hook(interrupt_hook, "after_settings")

        _emit(progress_callback, "Ověřuji obnovenou instance…")
        update_recovery_marker_phase(marker_file, "post_check")
        _call_hook(interrupt_hook, "before_postcheck")
        live_integrity = _verify_live_workspace(
            workspace_root,
            expected_db_size=metadata.database_size,
        )
        _call_hook(interrupt_hook, "after_postcheck")

        # Úspěch – teprve teď smíme smazat rollback kopii
        update_recovery_marker_phase(marker_file, "cleanup")
        rollback_removed = True
        if rollback_workspace is not None and rollback_workspace.exists():
            if keep_previous:
                notes.append(f"Původní data ponechána v {rollback_workspace}")
                rollback_removed = False
            else:
                if not _cleanup_tree(rollback_workspace):
                    rollback_removed = False
                    warnings.append(
                        f"Obnova úspěšná, ale rollback kopii se nepodařilo smazat: "
                        f"{rollback_workspace}"
                    )
                else:
                    rollback_workspace = None

        if settings_backup is not None:
            try:
                settings_backup.unlink(missing_ok=True)
                settings_backup = None
            except OSError as exc:
                warnings.append(f"Nepodařilo se smazat zálohu settings: {exc}")

        _cleanup_tree(extract_dir)
        extract_dir = None

        remove_recovery_marker(marker_file)
        marker_file = None
        _call_hook(interrupt_hook, "after_cleanup")

        # sjednocení notes/warnings pro kompatibilitu
        all_notes = list(notes) + list(warnings)

        return RestoreInstanceBackupResult(
            workspace_root=workspace_root,
            database_path=workspace_root / "databaze" / "manager_bozp.db",
            settings_path=restored_settings,
            package_path=package,
            integrity=report,
            database_integrity=live_integrity or prepared_integrity,
            preserved_backups_dir=preserved,
            notes=all_notes,
            restored=True,
            post_check_ok=True,
            rollback_copy_removed=rollback_removed,
            warnings=list(warnings),
            recovery_marker_removed=True,
        )

    except InstanceRestoreError as exc:
        if not swap_done:
            # Před přepnutím – úklid temp, původní data beze změny
            _cleanup_tree(new_workspace)
            _cleanup_tree(extract_dir)
            if settings_backup is not None:
                settings_backup.unlink(missing_ok=True)
            remove_recovery_marker(marker_file)
            # rollback_workspace by neměl existovat; pokud ano a current chybí, vrať
            if (
                rollback_workspace is not None
                and rollback_workspace.exists()
                and not workspace_root.exists()
            ):
                try:
                    os.rename(rollback_workspace, workspace_root)
                except OSError:
                    pass
            elif rollback_workspace is not None and rollback_workspace.exists():
                _cleanup_tree(rollback_workspace)
            raise _as_before_swap_error(exc) from exc

        # Po přepnutí – automatický rollback
        assert rollback_workspace is not None
        failed_dir = parent / f".{workspace_root.name}.mbrestore-failed-{token}"
        try:
            _perform_rollback(
                workspace_root=workspace_root,
                rollback_workspace=rollback_workspace,
                failed_workspace=failed_dir,
                settings_path=settings_path,
                settings_backup=settings_backup,
                marker_file=marker_file,
                interrupt_hook=interrupt_hook,
            )
            _cleanup_tree(extract_dir)
            raise InstanceRestoreError(
                RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK,
                (
                    f"Obnova selhala po přepnutí ({exc.code}): "
                    + str(exc).removeprefix(f"[{exc.code}] ").strip()
                ),
                phase=exc.phase or "after_swap",
                rolled_back=True,
                cause_code=exc.code,
            ) from exc
        except InstanceRestoreError as rollback_exc:
            if rollback_exc.code == RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK:
                raise
            # Selhání rollbacku – nic nemaž
            raise
    except BackupPackageVerificationError as exc:
        remove_recovery_marker(marker_file)
        raise InstanceRestoreError(
            RESTORE_ERR_FAILED_BEFORE_SWAP,
            str(exc),
            phase="integrity",
            cause_code=RESTORE_ERR_INTEGRITY,
        ) from exc
    except InterruptedError as exc:
        if swap_done and rollback_workspace is not None:
            failed_dir = parent / f".{workspace_root.name}.mbrestore-failed-{token}"
            try:
                _perform_rollback(
                    workspace_root=workspace_root,
                    rollback_workspace=rollback_workspace,
                    failed_workspace=failed_dir,
                    settings_path=settings_path,
                    settings_backup=settings_backup,
                    marker_file=marker_file,
                    interrupt_hook=interrupt_hook,
                )
                raise InstanceRestoreError(
                    RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK,
                    f"Obnova přerušena po přepnutí: {exc}",
                    phase="interrupted",
                    rolled_back=True,
                    cause_code=RESTORE_ERR_INTERRUPTED,
                ) from exc
            except InstanceRestoreError as rollback_exc:
                if rollback_exc.code == RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK:
                    raise
                raise
        _cleanup_tree(new_workspace)
        _cleanup_tree(extract_dir)
        if settings_backup is not None:
            settings_backup.unlink(missing_ok=True)
        remove_recovery_marker(marker_file)
        raise InstanceRestoreError(
            RESTORE_ERR_FAILED_BEFORE_SWAP,
            str(exc) or "Obnova přerušena.",
            phase="interrupted",
            cause_code=RESTORE_ERR_INTERRUPTED,
        ) from exc
    except OSError as exc:
        err = getattr(exc, "errno", None)
        code = RESTORE_ERR_DISK_FULL if err in {28, 112} else RESTORE_ERR_WRITE_ERROR
        wrapped = InstanceRestoreError(
            code,
            f"Chyba zápisu při obnově: {exc}",
            phase="io",
        )
        if not swap_done:
            _cleanup_tree(new_workspace)
            _cleanup_tree(extract_dir)
            if settings_backup is not None:
                settings_backup.unlink(missing_ok=True)
            remove_recovery_marker(marker_file)
            raise _as_before_swap_error(wrapped) from exc
        assert rollback_workspace is not None
        failed_dir = parent / f".{workspace_root.name}.mbrestore-failed-{token}"
        try:
            _perform_rollback(
                workspace_root=workspace_root,
                rollback_workspace=rollback_workspace,
                failed_workspace=failed_dir,
                settings_path=settings_path,
                settings_backup=settings_backup,
                marker_file=marker_file,
                interrupt_hook=interrupt_hook,
            )
            raise InstanceRestoreError(
                RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK,
                str(wrapped),
                phase="after_swap",
                rolled_back=True,
                cause_code=code,
            ) from exc
        except InstanceRestoreError as rollback_exc:
            if rollback_exc.code == RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK:
                raise
            raise
