"""Pomocníci pro bezpečné dočasné adresáře v testech (systémový temp + úklid)."""

from __future__ import annotations

import atexit
import shutil
import tempfile
from pathlib import Path

_REGISTERED: list[Path] = []
_CLEANUP_REGISTERED = False


def _cleanup_registered_temp_dirs() -> None:
    for path in _REGISTERED:
        shutil.rmtree(path, ignore_errors=True)
    _REGISTERED.clear()


def _ensure_cleanup_registered() -> None:
    global _CLEANUP_REGISTERED
    if not _CLEANUP_REGISTERED:
        atexit.register(_cleanup_registered_temp_dirs)
        _CLEANUP_REGISTERED = True


def create_tracked_temp_dir() -> Path:
    """Vytvoří adresář v systémovém temp a zaregistruje jeho smazání při ukončení."""
    _ensure_cleanup_registered()
    path = Path(tempfile.mkdtemp())
    _REGISTERED.append(path)
    return path
