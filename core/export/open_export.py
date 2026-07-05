import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget

_READY_ATTEMPTS = 20
_READY_SLEEP_SECONDS = 0.05

_APPIMAGE_ENV_KEYS = (
    "APPIMAGE",
    "APPDIR",
    "ARGV0",
    "LD_LIBRARY_PATH",
    "PYTHONHOME",
    "PYTHONPATH",
    "PERLLIB",
    "GST_PLUGIN_PATH",
    "GST_PLUGIN_SYSTEM_PATH",
)

_APPIMAGE_PATH_ENV_KEYS = (
    "PATH",
    "XDG_DATA_DIRS",
    "XDG_CONFIG_DIRS",
    "QT_PLUGIN_PATH",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "GTK_PATH",
    "GI_TYPELIB_PATH",
    "GSETTINGS_SCHEMA_DIR",
)

_SYSTEM_BIN_DIRS = ("/usr/local/bin", "/usr/bin", "/bin", "/snap/bin")


def _is_appimage() -> bool:
    return bool(os.environ.get("APPIMAGE"))


def _is_appimage_path_entry(entry: str) -> bool:
    if not entry:
        return True
    if ".mount_" in entry:
        return True
    appdir = os.environ.get("APPDIR", "")
    if appdir and (entry == appdir or entry.startswith(f"{appdir}{os.sep}")):
        return True
    return False


def _strip_appimage_path_entries(path_value: str) -> str:
    entries = [
        entry
        for entry in path_value.split(os.pathsep)
        if not _is_appimage_path_entry(entry)
    ]
    if entries:
        return os.pathsep.join(entries)
    return os.pathsep.join(_SYSTEM_BIN_DIRS)


def _cleaned_system_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in _APPIMAGE_ENV_KEYS:
        env.pop(key, None)

    for key in _APPIMAGE_PATH_ENV_KEYS:
        if key in env:
            env[key] = _strip_appimage_path_entries(env[key])

    if not env.get("PATH"):
        env["PATH"] = os.pathsep.join(_SYSTEM_BIN_DIRS)
    return env


def _system_binary(*names: str) -> str | None:
    env = _cleaned_system_env()
    for directory in _SYSTEM_BIN_DIRS:
        for name in names:
            candidate = Path(directory) / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    for name in names:
        found = shutil.which(name, path=env.get("PATH"))
        if found and not _is_appimage_path_entry(found):
            return found
    return None


def _wait_for_export_file_ready(path: Path) -> bool:
    for _ in range(_READY_ATTEMPTS):
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(_READY_SLEEP_SECONDS)
    return path.exists() and path.stat().st_size > 0


def _run_detached(command: list[str], *, env: dict[str, str] | None = None) -> bool:
    try:
        subprocess.Popen(
            command,
            shell=False,
            env=env,
            start_new_session=True,
            close_fds=True,
        )
        return True
    except OSError:
        return False


def _open_with_gio(path: Path, env: dict[str, str]) -> bool:
    gio = _system_binary("gio")
    if not gio:
        return False
    return _run_detached([gio, "open", str(path)], env=env)


def _open_with_system_xdg_open(path: Path, env: dict[str, str]) -> bool:
    xdg_open = _system_binary("xdg-open")
    if not xdg_open:
        return False
    return _run_detached([xdg_open, str(path)], env=env)


def _open_with_snap_libreoffice(path: Path, env: dict[str, str]) -> bool:
    snap = _system_binary("snap")
    libreoffice = _system_binary("libreoffice")
    if not snap or not libreoffice or "/snap/" not in libreoffice:
        return False
    return _run_detached(
        [snap, "run", "libreoffice", "--writer", str(path)],
        env=env,
    )


def _open_with_libreoffice(path: Path, env: dict[str, str]) -> bool:
    for name in ("libreoffice", "soffice"):
        executable = _system_binary(name)
        if not executable:
            continue
        if _run_detached([executable, "--writer", str(path)], env=env):
            return True
    return False


def _open_appimage_odt(path: Path) -> bool:
    env = _cleaned_system_env()

    openers = (
        lambda: _open_with_gio(path, env),
        lambda: _open_with_system_xdg_open(path, env),
        lambda: _open_with_snap_libreoffice(path, env),
        lambda: _open_with_libreoffice(path, env),
        lambda: _open_appimage_odt_via_tmp_copy(path, env),
    )
    for opener in openers:
        if opener():
            return True
    return False


def _open_appimage_odt_via_tmp_copy(path: Path, env: dict[str, str]) -> bool:
    tmp_path = Path(tempfile.gettempdir()) / f"manazer-bozp-{uuid.uuid4().hex}-{path.name}"
    try:
        shutil.copy2(path, tmp_path)
        os.chmod(tmp_path, 0o644)
    except OSError:
        return False

    return (
        _open_with_gio(tmp_path, env)
        or _open_with_system_xdg_open(tmp_path, env)
        or _open_with_snap_libreoffice(tmp_path, env)
        or _open_with_libreoffice(tmp_path, env)
    )


def _open_with_xdg_open(path: Path) -> bool:
    env = _cleaned_system_env() if _is_appimage() else None
    xdg_open = _system_binary("xdg-open") if _is_appimage() else shutil.which("xdg-open")
    if not xdg_open:
        return False
    return _run_detached([xdg_open, str(path)], env=env)


def _open_with_qt_desktop(path: Path) -> bool:
    try:
        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))
    except Exception:
        return False


def _show_open_failed(parent: QWidget | None, title: str, path: Path) -> None:
    QMessageBox.warning(
        parent,
        title,
        (
            "Export byl vytvořen, ale nepodařilo se ho automaticky otevřít.\n\n"
            f"Soubor:\n{path}"
        ),
    )


def open_export_file(path: Path | str, *, parent: QWidget | None = None, title: str = "Export") -> bool:
    """Open an exported file using a normalized absolute path."""
    resolved = Path(path).resolve()

    if not _wait_for_export_file_ready(resolved):
        QMessageBox.warning(
            parent,
            title,
            f"Soubor nebyl nalezen nebo ještě není připraven k otevření:\n{resolved}",
        )
        return False

    if _is_appimage() and resolved.suffix.lower() == ".odt":
        opened = _open_appimage_odt(resolved)
        if not opened:
            _show_open_failed(parent, title, resolved)
        return opened

    if sys.platform.startswith("linux"):
        if _open_with_xdg_open(resolved):
            return True
        opened = _open_with_qt_desktop(resolved)
    else:
        opened = _open_with_qt_desktop(resolved)
        if not opened:
            opened = _open_with_xdg_open(resolved)

    if not opened:
        _show_open_failed(parent, title, resolved)
    return opened
