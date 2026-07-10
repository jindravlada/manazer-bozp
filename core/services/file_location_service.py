from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

from core.export.open_export import (
    _cleaned_system_env,
    _is_appimage,
    _run_detached,
    _system_binary,
)

_logger = logging.getLogger(__name__)


def _linux_external_env() -> dict[str, str]:
    if _is_appimage():
        return _cleaned_system_env()
    return os.environ.copy()


def _attempt_commands(
    commands: list[list[str]],
    *,
    env: dict[str, str] | None,
) -> tuple[bool, list[str], str]:
    attempts: list[str] = []
    errors: list[str] = []

    for command in commands:
        if not command:
            continue
        attempts.append(" ".join(command))
        if not _run_detached(command, env=env):
            errors.append(f"{command[0]}: spuštění se nezdařilo")
            continue
        return True, attempts, ""

    return False, attempts, "; ".join(errors)


def _build_linux_directory_commands(directory: Path) -> list[list[str]]:
    resolved = str(directory.resolve())
    commands: list[list[str]] = []

    gio = _system_binary("gio")
    if gio:
        commands.append([gio, "open", resolved])

    xdg_open = _system_binary("xdg-open")
    if xdg_open:
        commands.append([xdg_open, resolved])

    for name in ("nautilus", "dolphin", "nemo", "thunar"):
        executable = _system_binary(name)
        if executable:
            commands.append([executable, resolved])

    return commands


def _build_linux_file_commands(file_path: Path) -> list[list[str]]:
    resolved = str(file_path.resolve())
    parent = str(file_path.resolve().parent)
    commands: list[list[str]] = []

    gio = _system_binary("gio")
    if gio:
        commands.append([gio, "open", parent])
        commands.append([gio, "open", resolved])

    xdg_open = _system_binary("xdg-open")
    if xdg_open:
        commands.append([xdg_open, parent])

    for name in ("nautilus", "dolphin", "nemo"):
        executable = _system_binary(name)
        if executable:
            commands.append([executable, "--select", resolved])

    thunar = _system_binary("thunar")
    if thunar:
        commands.append([thunar, parent])

    return commands


def _open_windows_path(path: Path) -> tuple[bool, list[str], str]:
    if path.is_dir():
        command = ["explorer.exe", str(path)]
    else:
        command = ["explorer.exe", "/select,", str(path)]
    opened, attempts, error = _attempt_commands([command], env=None)
    return opened, attempts, error


def _open_linux_path(path: Path) -> tuple[bool, list[str], str]:
    env = _linux_external_env()
    if path.is_dir():
        commands = _build_linux_directory_commands(path)
    else:
        commands = _build_linux_file_commands(path)
    return _attempt_commands(commands, env=env)


def _open_darwin_path(path: Path) -> tuple[bool, list[str], str]:
    if path.is_dir():
        command = ["open", str(path)]
    else:
        command = ["open", "-R", str(path)]
    return _attempt_commands([command], env=None)


def _open_in_file_manager(path: Path) -> tuple[bool, list[str], str]:
    if sys.platform.startswith("win"):
        return _open_windows_path(path)
    if sys.platform == "darwin":
        return _open_darwin_path(path)
    return _open_linux_path(path)


def _is_empty_path(path: Path | str | None) -> bool:
    if path is None:
        return True
    return not str(path).strip()


def _resolve_existing_target(path: Path) -> tuple[Path | None, Path | None]:
    if path.exists():
        return path, None

    parent = path.parent
    if parent.exists() and parent.is_dir():
        return None, parent
    return None, None


def open_path_in_file_manager(
    path: Path | str,
    *,
    parent: QWidget | None = None,
    title: str = "Umístění",
) -> bool:
    """Otevře správce souborů a pokud to OS podporuje, označí daný soubor."""
    if _is_empty_path(path):
        return False

    requested = Path(path)
    try:
        resolved = requested.resolve()
    except OSError:
        resolved = requested

    target, parent_directory = _resolve_existing_target(resolved)
    if target is None and parent_directory is None:
        QMessageBox.warning(
            parent,
            title,
            f"Soubor nebyl nalezen:\n{resolved}",
        )
        return False

    if target is None and parent_directory is not None:
        answer = QMessageBox.question(
            parent,
            title,
            f"Soubor nebyl nalezen:\n{resolved}\n\n"
            f"Otevřít nadřazenou složku?\n{parent_directory}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return False
        target = parent_directory

    assert target is not None
    opened, attempts, error = _open_in_file_manager(target)

    if opened:
        _logger.info("Otevřeno umístění: %s (příkazy: %s)", target, "; ".join(attempts))
        return True

    detail = error or "nebyl nalezen vhodný systémový příkaz"
    if attempts:
        detail = f"{detail}; pokusy: {' | '.join(attempts)}"
    _logger.warning("Umístění se nepodařilo otevřít (%s): %s", target, detail)
    QMessageBox.warning(
        parent,
        title,
        "Umístění se nepodařilo otevřít.",
    )
    return False
