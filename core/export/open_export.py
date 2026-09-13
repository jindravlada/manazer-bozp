import atexit
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

logger = logging.getLogger(__name__)

OPEN_EXPORT_TEMP_PREFIX = "manazer-bozp-"
_OPEN_EXPORT_TEMP_NAME = re.compile(r"^manazer-bozp-[0-9a-f]{32}-.+$")
_TEMP_FILE_MODE = 0o600
_created_temp_copies: set[str] = set()
_atexit_registered = False
_about_to_quit_connected = False

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


def _open_export_temp_dir() -> Path:
    return Path(tempfile.gettempdir())


def is_open_export_temp_name(name: str) -> bool:
    """True, pokud název patří tomuto AppImage fallback mechanismu."""
    return bool(_OPEN_EXPORT_TEMP_NAME.fullmatch(name))


def _ensure_atexit_cleanup() -> None:
    global _atexit_registered
    if _atexit_registered:
        return
    atexit.register(cleanup_tracked_open_export_temps)
    _atexit_registered = True


def install_open_export_temp_cleanup(app: QApplication | None = None) -> None:
    """Zaregistruje úklid temp kopií při ukončení procesu i Qt aplikace."""
    global _about_to_quit_connected
    _ensure_atexit_cleanup()
    if app is None:
        app = QApplication.instance()
    if app is None or _about_to_quit_connected:
        return
    try:
        app.aboutToQuit.connect(cleanup_tracked_open_export_temps)
        _about_to_quit_connected = True
    except Exception:
        logger.warning("Nepodařilo se napojit úklid temp souborů na aboutToQuit.", exc_info=True)


def _unlink_temp_copy(path: Path) -> None:
    _created_temp_copies.discard(str(path))
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError:
        logger.warning("Nelze ověřit temp soubor %s.", path, exc_info=True)
        return
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return
    try:
        os.unlink(path)
    except FileNotFoundError:
        return
    except OSError:
        logger.warning("Nepodařilo se odstranit temp soubor %s.", path, exc_info=True)


def cleanup_tracked_open_export_temps() -> None:
    """Odstraní temp kopie evidované v aktuálním běhu. Chyba nesmí padat ven."""
    try:
        remaining = list(_created_temp_copies)
        for raw in remaining:
            _unlink_temp_copy(Path(raw))
    except Exception:
        logger.warning("Úklid evidovaných temp souborů selhal.", exc_info=True)


def cleanup_orphan_open_export_temps() -> None:
    """Při startu smaže osiřelé vlastní `manazer-bozp-*` kopie. Nesmí shodit aplikaci."""
    try:
        root = _open_export_temp_dir()
        try:
            entries = os.scandir(root)
        except OSError:
            logger.warning("Nelze číst temp adresář %s.", root, exc_info=True)
            return
        with entries:
            for entry in entries:
                if not is_open_export_temp_name(entry.name):
                    continue
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                    continue
                try:
                    os.unlink(entry.path)
                except FileNotFoundError:
                    continue
                except OSError:
                    logger.warning(
                        "Nepodařilo se odstranit osiřelý temp soubor %s.",
                        entry.path,
                        exc_info=True,
                    )
    except Exception:
        logger.warning("Úklid osiřelých temp souborů selhal.", exc_info=True)


def _temp_copy_filename(source: Path) -> str:
    raw = Path(str(source.name or "soubor")).name.replace("\x00", "") or "soubor"
    prefix = f"{OPEN_EXPORT_TEMP_PREFIX}{uuid.uuid4().hex}-"
    encoded = raw.encode("utf-8")
    max_bytes = max(1, 255 - len(prefix.encode("utf-8")))
    while len(encoded) > max_bytes and raw:
        raw = raw[:-1]
        encoded = raw.encode("utf-8")
    return prefix + raw


def create_open_export_temp_copy(source: Path) -> Path | None:
    """Vytvoří soukromou temp kopii (mode 0600) a zaeviduje ji k úklidu."""
    _ensure_atexit_cleanup()
    tmp_dir = _open_export_temp_dir()
    tmp_path = tmp_dir / _temp_copy_filename(source)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(tmp_path, flags, _TEMP_FILE_MODE)
    except OSError:
        return None
    try:
        try:
            os.fchmod(fd, _TEMP_FILE_MODE)
        except OSError:
            pass
        with os.fdopen(fd, "wb") as dest, source.open("rb") as src:
            shutil.copyfileobj(src, dest)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return None
    _created_temp_copies.add(str(tmp_path))
    return tmp_path


def _open_via_private_temp_copy(
    path: Path,
    env: dict[str, str],
    *,
    include_office: bool,
) -> bool:
    tmp_path = create_open_export_temp_copy(path)
    if tmp_path is None:
        return False
    opened = _open_with_gio(tmp_path, env) or _open_with_system_xdg_open(tmp_path, env)
    if include_office and not opened:
        opened = _open_with_snap_libreoffice(tmp_path, env) or _open_with_libreoffice(
            tmp_path, env
        )
    if not opened:
        _unlink_temp_copy(tmp_path)
    return opened


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
    popen_kwargs: dict = {
        "shell": False,
        "env": env,
    }
    if sys.platform.startswith("linux"):
        popen_kwargs["start_new_session"] = True
        popen_kwargs["close_fds"] = True

    try:
        subprocess.Popen(command, **popen_kwargs)
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
        lambda: _open_via_private_temp_copy(path, env, include_office=True),
    )
    for opener in openers:
        if opener():
            return True
    return False


def _open_appimage_attachment(path: Path) -> bool:
    env = _cleaned_system_env()
    openers = (
        lambda: _open_with_gio(path, env),
        lambda: _open_with_system_xdg_open(path, env),
        lambda: _open_via_private_temp_copy(path, env, include_office=False),
        lambda: _open_with_qt_desktop(path),
    )
    for opener in openers:
        if opener():
            return True
    return False


def _open_appimage_file(path: Path) -> bool:
    if path.suffix.lower() == ".odt":
        return _open_appimage_odt(path)
    return _open_appimage_attachment(path)


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


def _show_open_failed(
    parent: QWidget | None,
    title: str,
    path: Path,
    *,
    is_export: bool = False,
) -> None:
    if is_export:
        message = (
            "Export byl vytvořen, ale nepodařilo se ho automaticky otevřít.\n\n"
            f"Soubor:\n{path}"
        )
    else:
        message = (
            "Soubor se nepodařilo otevřít.\n\n"
            f"Soubor:\n{path}"
        )

    QMessageBox.warning(parent, title, message)


def open_local_file(
    path: Path | str,
    *,
    parent: QWidget | None = None,
    title: str = "Soubor",
    failure_context: str = "file",
    show_error: bool = True,
) -> bool:
    """Open a local file with a system handler, isolated from AppImage env on Linux."""
    resolved = Path(path).resolve()

    if not resolved.exists():
        if show_error:
            QMessageBox.warning(
                parent,
                title,
                f"Soubor nebyl nalezen:\n{resolved}",
            )
        return False

    if _is_appimage():
        opened = _open_appimage_file(resolved)
    elif sys.platform.startswith("linux"):
        opened = _open_with_xdg_open(resolved) or _open_with_qt_desktop(resolved)
    else:
        opened = _open_with_qt_desktop(resolved) or _open_with_xdg_open(resolved)

    if not opened and show_error:
        _show_open_failed(
            parent,
            title,
            resolved,
            is_export=failure_context == "export",
        )
    return opened


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

    return open_local_file(
        resolved,
        parent=parent,
        title=title,
        failure_context="export",
    )
