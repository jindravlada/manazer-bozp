"""Recovery marker probíhající obnovy ``*.mbbackup`` (BACKUP-2b).

Marker leží mimo přepínaný workspace. Automatické řešení při startu aplikace
zatím není – pouze bezpečný a čitelný formát pro budoucí použití.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.backup.constants import (
    RESTORE_MARKER_FORMAT_VERSION,
    RESTORE_MARKER_KIND,
)


class RecoveryMarkerError(ValueError):
    """Neplatný recovery marker."""


def recovery_marker_path(parent_dir: Path, token: str) -> Path:
    """Cesta k markeru vedle workspace (mimo přepínaný kořen)."""
    return Path(parent_dir) / f".mbrestore-in-progress-{token}.json"


def build_recovery_marker_payload(
    *,
    phase: str,
    started_at: str,
    backup_format_version: int | None,
    package_path: str | Path,
    workspace_root: str | Path,
    new_workspace: str | Path | None,
    rollback_workspace: str | Path | None,
    settings_path: str | Path | None = None,
    settings_backup: str | Path | None = None,
    extract_dir: str | Path | None = None,
    token: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sestaví JSON-serializovatelný obsah markeru (jen technické údaje)."""
    payload: dict[str, Any] = {
        "marker_format_version": RESTORE_MARKER_FORMAT_VERSION,
        "kind": RESTORE_MARKER_KIND,
        "phase": phase,
        "started_at": started_at,
        "backup_format_version": backup_format_version,
        "package_path": str(package_path),
        "workspace_root": str(workspace_root),
        "new_workspace": str(new_workspace) if new_workspace else None,
        "rollback_workspace": str(rollback_workspace) if rollback_workspace else None,
        "settings_path": str(settings_path) if settings_path else None,
        "settings_backup": str(settings_backup) if settings_backup else None,
        "extract_dir": str(extract_dir) if extract_dir else None,
        "token": token,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def write_recovery_marker(path: Path, payload: dict[str, Any]) -> None:
    """Atomicky zapíše marker (temp + replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def read_recovery_marker(path: Path) -> dict[str, Any]:
    """Načte a základní validací ověří marker."""
    path = Path(path)
    if not path.is_file():
        raise RecoveryMarkerError(f"Marker neexistuje: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryMarkerError(f"Marker nelze načíst: {exc}") from exc
    if not isinstance(data, dict):
        raise RecoveryMarkerError("Marker musí být JSON objekt.")
    if data.get("kind") != RESTORE_MARKER_KIND:
        raise RecoveryMarkerError(f"Neočekávaný kind markeru: {data.get('kind')!r}")
    if "phase" not in data or "workspace_root" not in data:
        raise RecoveryMarkerError("Marker postrádá povinná pole phase/workspace_root.")
    return data


def update_recovery_marker_phase(path: Path, phase: str, **updates: Any) -> dict[str, Any]:
    """Aktualizuje fázi (a volitelná pole) v existujícím markeru."""
    data = read_recovery_marker(path)
    data["phase"] = phase
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    for key, value in updates.items():
        if value is None and key in data:
            data[key] = None
        elif value is not None:
            data[key] = str(value) if isinstance(value, Path) else value
    write_recovery_marker(path, data)
    return data


def remove_recovery_marker(path: Path | None) -> None:
    """Odstraní marker, pokud existuje."""
    if path is None:
        return
    path = Path(path)
    if path.exists():
        path.unlink(missing_ok=True)


def find_recovery_markers(parent_dir: str | Path | None = None) -> list[Path]:
    """
    Najde všechny recovery markery vedle workspace.

    Výchozí umístění: rodič ``StorageService.base``.
    """
    if parent_dir is None:
        from core.services.storage_service import storage_service

        parent = storage_service.base.parent
    else:
        parent = Path(parent_dir)
    if not parent.is_dir():
        return []
    return sorted(parent.glob(".mbrestore-in-progress-*.json"))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
