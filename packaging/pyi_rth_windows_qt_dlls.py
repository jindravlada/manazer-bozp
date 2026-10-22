"""Přidá složky Qt do hledání DLL dřív, než se importuje QtWidgets."""


def register_windows_dll_directories(base, add_dll_directory, isdir, join):
    added = []
    for relative in ("", "PySide6", "shiboken6"):
        directory = base if relative == "" else join(base, relative)
        if isdir(directory):
            add_dll_directory(directory)
            added.append(directory)
    return added


def _pyi_rthook():
    import os
    import sys

    if not sys.platform.startswith("win"):
        return
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return
    register_windows_dll_directories(
        base,
        os.add_dll_directory,
        os.path.isdir,
        os.path.join,
    )


_pyi_rthook()
del _pyi_rthook
