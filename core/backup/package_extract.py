"""Bezpečné rozbalení členů ZIP balíčku ``*.mbbackup`` (bez extractall)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from core.backup.paths import BackupPathError, normalize_archive_path


class SafeExtractError(ValueError):
    """Chyba při bezpečném rozbalení archivu."""


def resolve_safe_destination(dest_root: Path, archive_path: str) -> Path:
    """
    Spočítá cílovou cestu pod ``dest_root`` a ověří, že neuniká z kořene.
    """
    normalized = normalize_archive_path(archive_path)
    root = dest_root.resolve()
    target = (dest_root / Path(*normalized.split("/"))).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise SafeExtractError(
            f"Cílová cesta uniká z kořene rozbalení: {archive_path!r}"
        ) from exc
    return target


def safe_extract_zip_member(
    zf: zipfile.ZipFile,
    member_name: str,
    dest_root: Path,
    *,
    chunk_size: int = 1024 * 1024,
) -> Path:
    """
    Rozbalí jeden soubor z ZIP do ``dest_root`` s kontrolou path traversal.

    Nepoužívá ``ZipFile.extract`` / ``extractall``.
    """
    if member_name.endswith("/"):
        raise SafeExtractError(f"Nelze rozbalit adresářovou položku: {member_name!r}")

    try:
        normalized = normalize_archive_path(member_name)
    except BackupPathError as exc:
        raise SafeExtractError(str(exc)) from exc

    target = resolve_safe_destination(dest_root, normalized)
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        with zf.open(member_name, "r") as source, open(target, "wb") as handle:
            while True:
                chunk = source.read(chunk_size)
                if not chunk:
                    break
                handle.write(chunk)
    except KeyError as exc:
        raise SafeExtractError(f"Člen archivu neexistuje: {member_name!r}") from exc
    except OSError as exc:
        raise SafeExtractError(f"Chyba zápisu při rozbalení {normalized}: {exc}") from exc

    return target


def safe_extract_listed_members(
    zf: zipfile.ZipFile,
    member_names: list[str],
    dest_root: Path,
) -> list[Path]:
    """Rozbalí seznam členů (souborů) bezpečně pod ``dest_root``."""
    written: list[Path] = []
    for name in member_names:
        if name.endswith("/"):
            continue
        written.append(safe_extract_zip_member(zf, name, dest_root))
    return written
