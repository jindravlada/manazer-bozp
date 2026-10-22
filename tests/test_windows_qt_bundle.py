"""Úplnost Windows balíčku Qt pro import QtWidgets na čistém systému."""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

from core.packaging.windows_qt_bundle import (
    REQUIRED_PLUGINS,
    REQUIRED_PYSIDE_DLLS,
    WindowsQtBundleError,
    bundle_entries,
    missing_runtime_files,
    pyinstaller_arguments,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOK = PROJECT_ROOT / "packaging" / "pyi_rth_windows_qt_dlls.py"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"dll")


def _populate_wheel(root: Path) -> tuple[Path, Path]:
    pyside = root / "PySide6"
    shiboken = root / "shiboken6"
    for name in REQUIRED_PYSIDE_DLLS:
        _touch(pyside / name)
    for relative in REQUIRED_PLUGINS:
        _touch(pyside / relative)
    _touch(pyside / "Qt6Network.dll")
    _touch(pyside / "Qt6Cored.dll")
    _touch(pyside / "plugins" / "platforms" / "qwindowsd.dll")
    _touch(pyside / "opengl32sw.dll")
    _touch(shiboken / "shiboken6.abi3.dll")
    return pyside, shiboken


def _populate_dist(dist: Path) -> None:
    root = dist / "_internal"
    for name in REQUIRED_PYSIDE_DLLS:
        _touch(root / "PySide6" / name)
    for relative in REQUIRED_PLUGINS:
        _touch(root / "PySide6" / relative)
    _touch(root / "PySide6" / "QtWidgets.pyd")
    _touch(root / "python3.dll")
    _touch(root / "shiboken6" / "shiboken6.abi3.dll")


class WindowsQtBundleTestCase(unittest.TestCase):
    def test_bundle_keeps_qt_dlls_next_to_pyside_and_skips_debug(self) -> None:
        pyside, shiboken = _populate_wheel(self._tmp())
        entries = bundle_entries(pyside, shiboken)
        destinations = {path.name: destination for path, destination in entries}
        self.assertEqual(destinations["Qt6Widgets.dll"], "PySide6")
        self.assertEqual(destinations["vcruntime140_1.dll"], "PySide6")
        self.assertEqual(destinations["qwindows.dll"], "PySide6/plugins/platforms")
        self.assertEqual(destinations["shiboken6.abi3.dll"], "shiboken6")
        self.assertEqual(destinations["opengl32sw.dll"], "PySide6")
        self.assertNotIn("Qt6Cored.dll", destinations)
        self.assertNotIn("qwindowsd.dll", destinations)

    def test_missing_runtime_in_the_wheel_is_reported(self) -> None:
        pyside, shiboken = _populate_wheel(self._tmp())
        (pyside / "vcruntime140_1.dll").unlink()
        with self.assertRaises(WindowsQtBundleError) as caught:
            bundle_entries(pyside, shiboken)
        self.assertIn("vcruntime140_1.dll", str(caught.exception))

    def test_pyinstaller_parser_accepts_binaries_and_rejects_at_file(self) -> None:
        from PyInstaller.__main__ import generate_parser, run

        parser = generate_parser()
        self.assertNotEqual(parser.fromfile_prefix_chars, "@")
        rejected = parser.parse_args(
            ["--onedir", r"@build\qt-binaries.args", "main.py"]
        )
        self.assertEqual(
            rejected.filenames,
            [r"@build\qt-binaries.args", "main.py"],
        )
        with self.assertRaises(SystemExit) as caught:
            run(["--onedir", "--noconfirm", r"@build\qt-binaries.args"])
        self.assertIn("Script file", str(caught.exception))
        self.assertIn("qt-binaries.args", str(caught.exception))

        pyside, shiboken = _populate_wheel(self._tmp())
        argv = pyinstaller_arguments(bundle_entries(pyside, shiboken))
        self.assertNotIn("@build\\qt-binaries.args", argv)
        parsed = parser.parse_args(argv)
        self.assertEqual(parsed.filenames, ["main.py"])
        self.assertIs(parsed.console, False)
        binaries = {Path(source).name: destination for source, destination in parsed.binaries}
        self.assertEqual(binaries["Qt6Widgets.dll"], "PySide6")
        self.assertEqual(binaries["vcruntime140_1.dll"], "PySide6")
        self.assertEqual(binaries["qwindows.dll"], "PySide6/plugins/platforms")
        self.assertEqual(binaries["shiboken6.abi3.dll"], "shiboken6")
        data_dirs = {Path(source).name for source, _destination in parsed.datas}
        self.assertTrue({"moduly", "core", "ciselniky", "zdroje"} <= data_dirs)
        self.assertTrue(
            any(hook.endswith("pyi_rth_windows_qt_dlls.py") for hook in parsed.runtime_hooks)
        )

    def test_complete_dist_passes_and_missing_plugin_fails(self) -> None:
        dist = self._tmp() / "ManazerBOZP"
        _populate_dist(dist)
        self.assertEqual(missing_runtime_files(dist), [])
        (dist / "_internal" / "PySide6" / "plugins" / "platforms" / "qwindows.dll").unlink()
        missing = missing_runtime_files(dist)
        self.assertIn("PySide6/plugins/platforms/qwindows.dll", missing)

    def test_runtime_hook_adds_the_bundle_and_both_packages(self) -> None:
        spec = importlib.util.spec_from_file_location("pyi_rth_windows_qt_dlls", HOOK)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        added = []

        def isdir(path: str) -> bool:
            return path in {"C:/app/_internal", "C:/app/_internal/PySide6"}

        result = module.register_windows_dll_directories(
            "C:/app/_internal",
            added.append,
            isdir,
            lambda left, right: f"{left}/{right}",
        )
        self.assertEqual(
            result,
            ["C:/app/_internal", "C:/app/_internal/PySide6"],
        )
        self.assertNotIn("C:/app/_internal/shiboken6", added)

    def test_windows_build_registers_dll_directories_and_checks_the_package(self) -> None:
        bat = (PROJECT_ROOT / "build_windows.bat").read_text(encoding="utf-8")
        hook = HOOK.read_text(encoding="utf-8")
        installer = (PROJECT_ROOT / "installer.iss").read_text(encoding="utf-8")
        generator = (PROJECT_ROOT / "generate_installer_iss.py").read_text(encoding="utf-8")
        command = pyinstaller_arguments([])
        self.assertEqual(
            command[command.index("--runtime-hook") + 1],
            r"packaging\pyi_rth_windows_qt_dlls.py",
        )
        self.assertIn("windows_qt_bundle --build", bat)
        self.assertNotIn("@build\\qt-binaries.args", bat)
        self.assertIn("windows_qt_bundle --check dist\\ManazerBOZP", bat)
        self.assertIn("os.add_dll_directory", hook)
        self.assertIn("PySide6", hook)
        self.assertIn("shiboken6", hook)
        for text in (installer, generator):
            self.assertIn("ArchitecturesAllowed=x64compatible", text)
            self.assertIn("MinVersion=10.0", text)
            self.assertIn("ArchitecturesInstallIn64BitMode=x64compatible", text)

    def test_windows_build_prepares_its_own_virtualenv_before_the_installer(self) -> None:
        bat = (PROJECT_ROOT / "build_windows.bat").read_text(encoding="utf-8")
        self.assertNotIn("call .venv\\Scripts\\activate", bat)
        self.assertIn('.venv\\Scripts\\python.exe', bat)
        self.assertIn("py -3.14 -m venv", bat)
        self.assertIn("python -m venv", bat)
        self.assertIn("sys.version_info[:2] == (3, 14)", bat)
        self.assertIn("-r requirements.txt -r requirements-build.txt", bat)
        self.assertIn("import PySide6, PyInstaller", bat)
        self.assertLess(
            bat.index(".venv\\Scripts\\python.exe"),
            bat.index("windows_qt_bundle --build"),
        )
        self.assertLess(
            bat.index("import PySide6, PyInstaller"),
            bat.index("windows_qt_bundle --build"),
        )
        self.assertLess(
            bat.index("windows_qt_bundle --check"),
            bat.index('"%ISCC%"'),
        )
        self.assertLess(bat.index("BUILD EXE SELHAL"), bat.index('"%ISCC%"'))

    def _tmp(self) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="windows-qt-"))
        self.addCleanup(lambda: shutil.rmtree(directory, ignore_errors=True))
        return directory
