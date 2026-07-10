import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget


def _run_command(command: list[str]) -> bool:
    try:
        subprocess.Popen(command, start_new_session=True, close_fds=True)
        return True
    except OSError:
        return False


def _linux_open_with_selection(path: Path) -> bool:
    resolved = str(path.resolve())
    parent = str(path.resolve().parent)

    commands = [
        ["nautilus", "--select", resolved],
        ["dolphin", "--select", resolved],
        ["nemo", "--select", resolved],
        ["thunar", parent],
        ["xdg-open", parent],
    ]
    for command in commands:
        executable = shutil.which(command[0])
        if executable:
            if _run_command([executable, *command[1:]]):
                return True
    return False


def open_path_in_file_manager(
    path: Path | str,
    *,
    parent: QWidget | None = None,
    title: str = "Umístění",
) -> bool:
    """Otevře správce souborů a pokud to OS podporuje, označí daný soubor."""
    resolved = Path(path).resolve()

    if not resolved.exists():
        QMessageBox.warning(
            parent,
            title,
            f"Soubor nebyl nalezen:\n{resolved}",
        )
        return False

    opened = False
    if sys.platform.startswith("win"):
        opened = _run_command(["explorer", "/select,", str(resolved)])
    elif sys.platform == "darwin":
        opened = _run_command(["open", "-R", str(resolved)])
    else:
        opened = _linux_open_with_selection(resolved)

    if not opened:
        QMessageBox.warning(
            parent,
            title,
            f"Umístění se nepodařilo otevřít.\n\nSoubor:\n{resolved}",
        )
    return opened
