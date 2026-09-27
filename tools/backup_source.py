#!/usr/bin/env python3
"""Vytvoří jeden ZIP se zdrojovým projektem Manažer BOZP včetně historie Gitu.

Spuštění z kořene projektu:
    python tools/backup_source.py

Skript projekt jen čte. Jediný zápis je adresář source_backups/ a výsledný ZIP.
Rozpracovaný soubor má příponu .partial a na finální název se přejmenuje
až po úspěšné kontrole integrity.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.version import APP_VERSION  # noqa: E402

BACKUPS_DIRNAME = "source_backups"
PARTIAL_SUFFIX = ".partial"

# Adresáře, které se do zálohy neberou (kdekoli ve stromu, kromě .git).
EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".venv",
        ".venv-oldlinux",
        "venv",
        "env",
        ".tox",
        ".nox",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".hypothesis",
        "htmlcov",
        ".eggs",
        "pip-wheel-metadata",
        "node_modules",
        "build",
        "dist",
        "build90a",
        "dist90a",
        "AppDir",
        "AppDir90a",
        "squashfs-root",
        "source_backups",
        ".test-tmp",
        "Zalohy",
        "ZZáloha",
        "Wokna",
        ".idea",
        ".vscode",
    }
)

_ROOT_TMP_DIR = re.compile(r"tmp[a-z0-9_]+")
_ROOT_ARCHIVE_ZIP = re.compile(
    r"(?i)^(?:managerbozp|manazerbozp|m-bozp|mb3[.\-]|mb-3[.\-]).+\.zip$"
)
_BACKUP_ARCHIVE = re.compile(
    r"(?i).*(?:backup|zaloh|záloh).*\.(?:zip|7z|tar|tgz|tar\.gz)$"
)
_SECRET_PARTS = frozenset(
    {
        "credential",
        "credentials",
        "secret",
        "secrets",
        "token",
        "tokens",
        "oauth",
        "password",
        "passwd",
        "pwd",
        "apikey",
    }
)
_SECRET_EXACT = frozenset(
    {
        ".netrc",
        ".pypirc",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
    }
)
_SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".kdbx")
_DATABASE_SUFFIXES = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".mbbackup",
    ".sqlite-shm",
    ".sqlite-wal",
)
_CACHE_SUFFIXES = (".pyc", ".pyo", ".log", ".tmp", ".bak", ".swp", ".swo")


class SourceBackupError(RuntimeError):
    """Zálohu se nepodařilo dokončit. Hotový ZIP se v tom případě nepublikuje."""


@dataclass(frozen=True)
class SourceBackupResult:
    path: Path
    version: str
    file_count: int
    size_bytes: int
    sha256: str


def source_backup_filename(version: str, when: datetime) -> str:
    stamp = when.strftime("%Y-%m-%d_%H%M")
    return f"Manazer_BOZP_source_{version}_{stamp}.zip"


def iter_source_files(project_root: Path):
    """Vrátí dvojice (cesta, jméno v ZIP) souborů určených k záloze."""
    root = project_root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        rel_dir = current.relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        inside_git = _is_git_path(rel_dir)
        kept_dirs: list[str] = []
        for name in dirnames:
            child_rel = f"{rel_dir}/{name}" if rel_dir else name
            if not inside_git and _directory_excluded(child_rel, name):
                continue
            kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in filenames:
            path = current / name
            if path.is_symlink() or not path.is_file():
                continue
            rel = f"{rel_dir}/{name}" if rel_dir else name
            if not inside_git and _file_excluded(rel):
                continue
            yield path, rel


def verify_zip(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            broken = archive.testzip()
    except zipfile.BadZipFile as exc:
        raise SourceBackupError("Kontrola integrity ZIP selhala.") from exc
    if broken is not None:
        raise SourceBackupError("Kontrola integrity ZIP selhala.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def format_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if unit == "GiB" or value < 1024:
            if unit == "B":
                return f"{size_bytes} B"
            return f"{value:.1f} {unit} ({size_bytes} B)"
        value /= 1024
    return f"{size_bytes} B"


def create_source_backup(
    project_root: Path,
    *,
    when: datetime | None = None,
) -> SourceBackupResult:
    """Zabalí zdrojový projekt. Při chybě nesmí zůstat soubor s příponou .zip."""
    root = project_root.resolve()
    moment = when or datetime.now()
    version = APP_VERSION
    final_name = source_backup_filename(version, moment)
    backups_dir = root / BACKUPS_DIRNAME
    backups_dir.mkdir(exist_ok=True)
    final_path = backups_dir / final_name
    partial_path = backups_dir / f".{final_name}.{os.getpid()}{PARTIAL_SUFFIX}"
    if final_path.exists():
        raise SourceBackupError(f"Soubor zálohy už existuje: {final_path}")

    files = list(iter_source_files(root))
    published = False
    try:
        with zipfile.ZipFile(
            partial_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as archive:
            for source, arcname in files:
                archive.write(source, arcname)
        verify_zip(partial_path)
        digest = sha256_file(partial_path)
        os.replace(partial_path, final_path)
        published = True
    except Exception as exc:
        if not published:
            partial_path.unlink(missing_ok=True)
        if isinstance(exc, SourceBackupError):
            raise
        raise SourceBackupError(str(exc)) from exc

    return SourceBackupResult(
        path=final_path,
        version=version,
        file_count=len(files),
        size_bytes=final_path.stat().st_size,
        sha256=digest,
    )


def format_report(result: SourceBackupResult) -> str:
    return "\n".join(
        (
            f"Cesta: {result.path}",
            f"Verze: {result.version}",
            f"Počet souborů: {result.file_count}",
            f"Velikost: {format_size(result.size_bytes)}",
            f"SHA-256: {result.sha256}",
            "Záloha zdrojového kódu byla úspěšně vytvořena.",
        )
    )


def main(argv: list[str] | None = None, *, project_root: Path | None = None) -> int:
    del argv
    root = PROJECT_ROOT if project_root is None else project_root
    try:
        result = create_source_backup(root)
    except SourceBackupError as exc:
        print(f"Záloha zdrojového kódu se nezdařila: {exc}", file=sys.stderr)
        return 1
    print(format_report(result))
    return 0


def _is_git_path(rel: str) -> bool:
    return rel == ".git" or rel.startswith(".git/")


def _directory_excluded(rel: str, name: str) -> bool:
    if name in EXCLUDED_DIRECTORY_NAMES or name.endswith(".egg-info"):
        return True
    if "/" not in rel and _ROOT_TMP_DIR.fullmatch(name):
        return True
    return False


def _file_excluded(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if _is_runtime_user_data(rel):
        return True
    if _is_secret(name):
        return True
    if name.lower().endswith(_DATABASE_SUFFIXES):
        return True
    if _is_backup_archive(name):
        return True
    if _is_regenerable_file(name, rel):
        return True
    return False


def _is_runtime_user_data(rel: str) -> bool:
    """V data/ zůstávají jen zástupné .gitkeep. Databáze, přílohy i lokální nastavení ne."""
    if not rel.startswith("data/"):
        return False
    return Path(rel).name != ".gitkeep"


def _is_secret(name: str) -> bool:
    lower = name.lower()
    if lower in _SECRET_EXACT or lower == ".env" or lower.startswith(".env."):
        return True
    if lower.endswith(_SECRET_SUFFIXES):
        return True
    parts = [part for part in re.split(r"[^a-z0-9]+", lower) if part]
    if "api" in parts and "key" in parts:
        return True
    return any(part in _SECRET_PARTS for part in parts)


def _is_backup_archive(name: str) -> bool:
    return bool(_ROOT_ARCHIVE_ZIP.match(name) or _BACKUP_ARCHIVE.match(name))


def _is_regenerable_file(name: str, rel: str) -> bool:
    lower = name.lower()
    if lower.endswith(".appimage") or lower.endswith(".exe"):
        return True
    if lower.endswith(".qm") and not rel.startswith("zdroje/preklady/"):
        return True
    if lower in {".ds_store", "thumbs.db", ".coverage", "coverage.xml"}:
        return True
    if lower.startswith(".coverage."):
        return True
    if lower.endswith(_CACHE_SUFFIXES) or lower.endswith(".partial"):
        return True
    if name.endswith("~") or "$py.class" in lower:
        return True
    return False


if __name__ == "__main__":
    sys.exit(main())
