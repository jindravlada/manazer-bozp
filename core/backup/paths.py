"""Bezpečná normalizace a validace relativních cest v záložním archivu."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath


class BackupPathError(ValueError):
    """Neplatná nebo nebezpečná cesta v balíčku zálohy."""


def normalize_archive_path(path: str | None) -> str:
    """
    Normalizuje cestu na relativní POSIX tvar bez nebezpečných segmentů.

    Povolené: ``database/manager_bozp.db``, ``workspace/prilohy/a/b.jpg``.
    Zamítnuté: absolutní cesty, ``..``, prázdné, Windows drive prefixy.
    """
    if path is None:
        raise BackupPathError("Cesta nesmí být prázdná.")

    raw = str(path).strip()
    if not raw:
        raise BackupPathError("Cesta nesmí být prázdná.")

    # Jednotný oddělovač pro kontrolu (Windows i POSIX zápis).
    unified = raw.replace("\\", "/")

    if unified.startswith("/") or unified.startswith("//"):
        raise BackupPathError(f"Absolutní cesta není povolena: {path!r}")

    # Windows UNC / drive (C:/…, \\server\share, …) i po sjednocení.
    windows = PureWindowsPath(raw)
    if windows.is_absolute() or windows.drive or windows.anchor:
        raise BackupPathError(f"Absolutní nebo Windows cesta mimo kořen: {path!r}")

    posix = PurePosixPath(unified)
    if posix.is_absolute():
        raise BackupPathError(f"Absolutní cesta není povolena: {path!r}")

    parts: list[str] = []
    for part in posix.parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise BackupPathError(f"Cesta nesmí obsahovat '..': {path!r}")
        if part.endswith(":") and len(part) <= 2:
            # pojistka pro segment typu „C:“
            raise BackupPathError(f"Absolutní nebo Windows cesta mimo kořen: {path!r}")
        parts.append(part)

    if not parts:
        raise BackupPathError("Cesta nesmí být prázdná.")

    return "/".join(parts)


def is_safe_archive_path(path: str | None) -> bool:
    try:
        normalize_archive_path(path)
        return True
    except BackupPathError:
        return False


def component_for_archive_path(normalized_path: str) -> str:
    """Vrátí kořenovou komponentu (první segment) normalizované cesty."""
    normalized = normalize_archive_path(normalized_path)
    return normalized.split("/", 1)[0]
