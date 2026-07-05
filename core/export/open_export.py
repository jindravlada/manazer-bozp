import os
import shutil
import subprocess
import sys
import time
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
)

_LIBREOFFICE_CANDIDATES = ("libreoffice", "soffice")


def _is_appimage() -> bool:
    return bool(os.environ.get("APPIMAGE"))


def _cleaned_system_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in _APPIMAGE_ENV_KEYS:
        env.pop(key, None)
    return env


def _find_executable(names: tuple[str, ...], env: dict[str, str]) -> str | None:
    for name in names:
        found = shutil.which(name, path=env.get("PATH"))
        if found:
            return found
    return None


def _wait_for_export_file_ready(path: Path) -> bool:
    for _ in range(_READY_ATTEMPTS):
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(_READY_SLEEP_SECONDS)
    return path.exists() and path.stat().st_size > 0


def _open_with_libreoffice(path: Path) -> bool:
    env = _cleaned_system_env()
    executable = _find_executable(_LIBREOFFICE_CANDIDATES, env)
    if not executable:
        return False

    try:
        subprocess.Popen(
            [executable, "--writer", str(path)],
            shell=False,
            env=env,
            start_new_session=True,
            close_fds=True,
        )
        return True
    except OSError:
        return False


def _open_with_xdg_open(path: Path) -> bool:
    xdg_open = shutil.which("xdg-open")
    if not xdg_open:
        return False

    try:
        subprocess.Popen(
            [xdg_open, str(path)],
            shell=False,
            start_new_session=True,
            close_fds=True,
        )
        return True
    except OSError:
        return False


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
        opened = _open_with_libreoffice(resolved)
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
