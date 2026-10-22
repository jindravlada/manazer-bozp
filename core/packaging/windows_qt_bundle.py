"""Knihovny Qt, bez kterých na čistém Windows spadne import QtWidgets.

PySide6 při startu zavolá ``os.add_dll_directory`` jen pro shiboken6. Tím
Windows přestane hledat DLL podle PATH a podle adresáře nastaveného
zavaděčem PyInstalleru. ``QtWidgets.pyd`` pak nenačte ``Qt6Widgets.dll``,
pokud neleží ve stejné složce nebo v přidaném adresáři DLL. Na počítači
bez redistribuovatelného balíčku Visual C++ stejně selže i ``Qt6Core.dll``,
když v balíčku chybí ``vcruntime140_1.dll`` a ``msvcp140.dll``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REQUIRED_PYSIDE_DLLS = (
    "Qt6Core.dll",
    "Qt6Gui.dll",
    "Qt6Widgets.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
)
REQUIRED_PLUGINS = (
    "plugins/platforms/qwindows.dll",
    "plugins/styles/qmodernwindowsstyle.dll",
)
OPTIONAL_PYSIDE_DLLS = (
    "concrt140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "vcomp140.dll",
    "opengl32sw.dll",
    "d3dcompiler_47.dll",
    "dxcompiler.dll",
    "dxil.dll",
)
PLUGIN_DIRECTORIES = (
    "plugins/platforms",
    "plugins/styles",
    "plugins/imageformats",
    "plugins/iconengines",
    "plugins/tls",
    "plugins/generic",
    "plugins/networkinformation",
    "plugins/platforminputcontexts",
)
PYSIDE_DEST = "PySide6"
SHIBOKEN_DEST = "shiboken6"


class WindowsQtBundleError(RuntimeError):
    """Balíček Qt pro Windows není úplný."""


def _is_debug_dll(path: Path) -> bool:
    name = path.name
    if not name.lower().endswith("d.dll"):
        return False
    release_name = (name[:-5] + ".dll").lower()
    return any(
        candidate.name.lower() == release_name
        for candidate in path.parent.glob("*.dll")
    )


def _existing_dlls(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.glob("*.dll")
        if path.is_file() and not _is_debug_dll(path)
    )


def bundle_entries(pyside_dir: Path, shiboken_dir: Path) -> list[tuple[Path, str]]:
    """Dvojice (zdroj, cílová složka v balíčku) pro ``--add-binary``."""
    missing = [
        relative
        for relative in (*REQUIRED_PYSIDE_DLLS, *REQUIRED_PLUGINS)
        if not (pyside_dir / relative).is_file()
    ]
    shiboken_dlls = [
        path
        for path in _existing_dlls(shiboken_dir)
        if path.name.lower().startswith("shiboken6")
    ]
    if not shiboken_dlls:
        missing.append("shiboken6/shiboken6*.dll")
    if missing:
        lines = "\n".join(f"- {item}" for item in missing)
        raise WindowsQtBundleError(
            "Instalace PySide6 neobsahuje knihovny potřebné pro čistá Windows.\n"
            f"{lines}"
        )

    entries: list[tuple[Path, str]] = []
    seen: set[Path] = set()

    def add(path: Path, destination: str) -> None:
        resolved = path.resolve()
        if resolved in seen or not path.is_file() or _is_debug_dll(path):
            return
        seen.add(resolved)
        entries.append((path, destination))

    for name in (*REQUIRED_PYSIDE_DLLS, *OPTIONAL_PYSIDE_DLLS):
        add(pyside_dir / name, PYSIDE_DEST)
    for path in _existing_dlls(pyside_dir):
        if path.name.lower().startswith("qt6"):
            add(path, PYSIDE_DEST)
    for relative in PLUGIN_DIRECTORIES:
        directory = pyside_dir / relative
        for path in _existing_dlls(directory):
            add(path, f"{PYSIDE_DEST}/{relative}")
    for path in shiboken_dlls:
        add(path, SHIBOKEN_DEST)
    return entries


def write_argfile(path: Path, entries: list[tuple[Path, str]]) -> None:
    lines: list[str] = []
    for source, destination in entries:
        lines.append("--add-binary")
        lines.append(f"{source};{destination}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def installed_bundle_entries() -> list[tuple[Path, str]]:
    import PySide6
    import shiboken6

    return bundle_entries(
        Path(PySide6.__file__).resolve().parent,
        Path(shiboken6.__file__).resolve().parent,
    )


def package_root(dist_dir: Path) -> Path:
    internal = dist_dir / "_internal"
    if internal.is_dir():
        return internal
    return dist_dir


def missing_runtime_files(dist_dir: Path) -> list[str]:
    """Cesty, které ve složce ``dist/ManazerBOZP`` chybí."""
    root = package_root(dist_dir)
    required = [
        f"{PYSIDE_DEST}/{name}" for name in REQUIRED_PYSIDE_DLLS
    ]
    required.extend(f"{PYSIDE_DEST}/{relative}" for relative in REQUIRED_PLUGINS)
    required.append(f"{PYSIDE_DEST}/QtWidgets.pyd")
    required.append("python3.dll")
    missing = [relative for relative in required if not (root / relative).is_file()]
    shiboken_dir = root / SHIBOKEN_DEST
    has_shiboken = any(
        path.name.lower().startswith("shiboken6")
        for path in _existing_dlls(shiboken_dir)
    )
    if not has_shiboken:
        missing.append(f"{SHIBOKEN_DEST}/shiboken6*.dll")
    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kontrola a seznam Qt knihoven pro Windows.")
    parser.add_argument("--argfile", type=Path, help="Zapíše argumenty --add-binary pro PyInstaller.")
    parser.add_argument("--check", type=Path, help="Složka dist/ManazerBOZP po sestavení.")
    args = parser.parse_args(argv)
    if args.argfile is None and args.check is None:
        parser.error("Zadejte --argfile nebo --check.")
    try:
        if args.argfile is not None:
            write_argfile(args.argfile, installed_bundle_entries())
        if args.check is not None:
            missing = missing_runtime_files(args.check)
            if missing:
                lines = "\n".join(f"- {item}" for item in missing)
                raise WindowsQtBundleError(
                    "Windows balíček neobsahuje knihovny Qt a běhové knihovny.\n"
                    "Na čistém Windows by import QtWidgets selhal.\n"
                    f"{lines}"
                )
    except WindowsQtBundleError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
