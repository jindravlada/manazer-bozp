"""SEC-HARDENING-BUILD-1: pin runtime/build tools and linuxdeploy SHA-256."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = PROJECT_ROOT / "packaging" / "verify_linuxdeploy.py"
PIN_FILE = PROJECT_ROOT / "packaging" / "linuxdeploy.pin"
LINUXDEPLOY = PROJECT_ROOT / "linuxdeploy-x86_64.AppImage"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
REQUIREMENTS_BUILD = PROJECT_ROOT / "requirements-build.txt"

_RUNTIME_PINS = {
    "PySide6": "6.11.2",
    "SQLAlchemy": "2.0.52",
    "requests": "2.34.2",
    "Pillow": "12.3.0",
}
_PYINSTALLER_VERSION = "6.22.3"
_APP_DATAS = ("moduly", "core", "ciselniky", "zdroje")


def _requirement_map(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name, sep, version = line.partition("==")
        if not sep:
            continue
        mapping[name.strip()] = version.strip()
    return mapping


class SecHardeningBuild1TestCase(unittest.TestCase):
    def test_a_runtime_requirements_are_pinned(self) -> None:
        mapping = _requirement_map(REQUIREMENTS)
        self.assertEqual(mapping, _RUNTIME_PINS)
        text = REQUIREMENTS.read_text(encoding="utf-8")
        for name in _RUNTIME_PINS:
            self.assertIsNone(re.search(rf"^{re.escape(name)}\s*$", text, flags=re.MULTILINE))

    def test_b_pillow_is_at_least_12_3_0(self) -> None:
        version = tuple(int(part) for part in _requirement_map(REQUIREMENTS)["Pillow"].split("."))
        self.assertGreaterEqual(version, (12, 3, 0))

    def test_c_pyinstaller_is_pinned_as_build_dependency(self) -> None:
        runtime = REQUIREMENTS.read_text(encoding="utf-8")
        build = _requirement_map(REQUIREMENTS_BUILD)
        self.assertNotIn("pyinstaller", runtime.lower())
        self.assertEqual(build["pyinstaller"], _PYINSTALLER_VERSION)
        old = (PROJECT_ROOT / "build_old_release.sh").read_text(encoding="utf-8")
        self.assertIn("pip install -r requirements-build.txt", old)
        self.assertNotIn("pip install pyinstaller", old)
        self.assertNotIn("pip install --upgrade pyinstaller", old)
        release = (PROJECT_ROOT / "build_release.sh").read_text(encoding="utf-8")
        self.assertIn("requirements-build.txt", release)

    def test_d_linuxdeploy_hash_mismatch_fails_and_match_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.bin"
            bad = Path(tmp) / "bad.bin"
            good.write_bytes(b"linuxdeploy-test-payload")
            bad.write_bytes(b"tampered")
            pin = Path(tmp) / "linuxdeploy.pin"
            digest = hashlib.sha256(good.read_bytes()).hexdigest()
            pin.write_text(f"LINUXDEPLOY_SHA256={digest}\n", encoding="utf-8")

            env_script = (
                "import sys\n"
                f"sys.path.insert(0, {str(PROJECT_ROOT / 'packaging')!r})\n"
                "from verify_linuxdeploy import verify_linuxdeploy\n"
                "from pathlib import Path\n"
                f"verify_linuxdeploy(Path({str(good)!r}), pin_path=Path({str(pin)!r}))\n"
            )
            ok = subprocess.run(
                [sys.executable, "-c", env_script],
                capture_output=True,
                text=True,
            )
            self.assertEqual(ok.returncode, 0, ok.stderr)

            fail_script = env_script.replace(str(good), str(bad))
            failed = subprocess.run(
                [sys.executable, "-c", fail_script],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("SHA-256 linuxdeploy nesouhlasí", failed.stderr)

        self.assertTrue(LINUXDEPLOY.is_file())
        real = subprocess.run(
            [sys.executable, str(VERIFY_SCRIPT), str(LINUXDEPLOY)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(real.returncode, 0, real.stderr)

        wrong_pin_run = subprocess.run(
            [sys.executable, str(VERIFY_SCRIPT), str(REQUIREMENTS)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(wrong_pin_run.returncode, 1)
        self.assertIn("SHA-256 linuxdeploy nesouhlasí", wrong_pin_run.stderr)

    def test_e_build_scripts_do_not_fetch_floating_continuous(self) -> None:
        for name in ("build_release.sh", "build_old_release.sh"):
            content = (PROJECT_ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("releases/download/continuous", content)
            self.assertIn("packaging/verify_linuxdeploy.py", content)
        pin = PIN_FILE.read_text(encoding="utf-8")
        self.assertIn("36a2d7e274d12e1050d0e9ecfe11d339ed54720b2bec464c286d53f8b07f5c62", pin)
        self.assertIn("is rewritten", pin)

    def test_f_linux_add_data_stays_complete(self) -> None:
        for name in ("build_release.sh", "build_old_release.sh"):
            content = (PROJECT_ROOT / name).read_text(encoding="utf-8")
            for folder in _APP_DATAS:
                self.assertIn(f'--add-data "{folder}:{folder}"', content)

    def test_g_windows_add_data_includes_the_same_app_data(self) -> None:
        content = (PROJECT_ROOT / "build_windows.bat").read_text(encoding="utf-8")
        for folder in _APP_DATAS:
            self.assertIn(f'--add-data "{folder};{folder}"', content)

    def test_h_existing_packaging_assertions_still_hold(self) -> None:
        release = (PROJECT_ROOT / "build_release.sh").read_text(encoding="utf-8")
        old = (PROJECT_ROOT / "build_old_release.sh").read_text(encoding="utf-8")
        self.assertIn("mktemp -d", release)
        self.assertIn("LINUXDEPLOY_WORKDIR", release)
        self.assertIn("trap cleanup_linuxdeploy_workdir EXIT", release)
        self.assertNotIn("./squashfs-root/AppRun", release)
        self.assertIn("mktemp -d", old)
        self.assertIn('rm -rf "$LINUXDEPLOY_WORKDIR" /src/squashfs-root', old)
        self.assertNotIn("./linuxdeploy-x86_64.AppImage --appimage-extract", old)
        self.assertIn("docker rm -f", old)
        self.assertIn("docker run --rm", old)


if __name__ == "__main__":
    unittest.main()
