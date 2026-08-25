"""Qt platform-theme pluginy pro nativní systémový výběr souborů a složek.

Cesty se berou z nainstalovaného PySide6, nikoli z absolutní cesty vývojářského
počítače. Do AppImage stačí plugin XDG Desktop Portal; GTK3 je volitelný
základní theme, nikoli celé desktopové prostředí.
"""

from __future__ import annotations

from pathlib import Path

PORTAL_PLUGIN = "libqxdgdesktopportal.so"
GTK3_PLUGIN = "libqgtk3.so"
PLUGIN_DEST = "PySide6/Qt/plugins/platformthemes"


def pyside6_platformthemes_dir() -> Path:
    import PySide6

    return Path(PySide6.__file__).resolve().parent / "Qt" / "plugins" / "platformthemes"


def plugin_path(filename: str) -> Path:
    return pyside6_platformthemes_dir() / filename


def pyinstaller_binaries(*, required: tuple[str, ...] = (PORTAL_PLUGIN,)) -> list[tuple[str, str]]:
    """Dvojice (zdroj, cíl) pro PyInstaller ``binaries=`` / ``--add-binary``."""
    directory = pyside6_platformthemes_dir()
    result: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(name: str, *, mandatory: bool) -> None:
        if name in seen:
            return
        path = directory / name
        if path.is_file():
            seen.add(name)
            result.append((str(path), PLUGIN_DEST))
            return
        if mandatory:
            raise FileNotFoundError(
                f"Chybí Qt platform-theme plugin {name} v {directory}."
            )

    for name in required:
        add(name, mandatory=True)
    add(GTK3_PLUGIN, mandatory=False)
    return result


def pyinstaller_binary_specs() -> list[str]:
    return [f"{src}:{dest}" for src, dest in pyinstaller_binaries()]
