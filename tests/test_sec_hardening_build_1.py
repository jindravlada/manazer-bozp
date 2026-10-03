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

        wrong_pin_run = subprocess.run(
            [sys.executable, str(VERIFY_SCRIPT), str(REQUIREMENTS)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(wrong_pin_run.returncode, 1)
        self.assertIn("SHA-256 linuxdeploy nesouhlasí", wrong_pin_run.stderr)

    def test_e_pin_uses_url_and_sha_not_asset_id(self) -> None:
        official_url = (
            "https://github.com/linuxdeploy/linuxdeploy/releases/download/"
            "continuous/linuxdeploy-x86_64.AppImage"
        )
        pinned_sha = "8aea8da0f7f7039d2a2cecb14657d752a222a5e1d3825caeef186c82f751cdd1"
        pin = PIN_FILE.read_text(encoding="utf-8")
        self.assertIn(f"LINUXDEPLOY_URL={official_url}", pin)
        self.assertIn(f"LINUXDEPLOY_SHA256={pinned_sha}", pin)
        self.assertNotIn("LINUXDEPLOY_GITHUB_ASSET_ID", pin)
        self.assertNotIn("538917371", pin)
        for name in ("build_release.sh", "build_old_release.sh"):
            content = (PROJECT_ROOT / name).read_text(encoding="utf-8")
            self.assertIn("packaging/verify_linuxdeploy.py", content)
            self.assertNotIn("538917371", content)
            self.assertNotIn("releases/assets/", content)
        release = (PROJECT_ROOT / "build_release.sh").read_text(encoding="utf-8")
        self.assertIn("--ensure", release)
        self.assertNotIn("releases/download/continuous", release)

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

    def _load_helpers(self):
        packaging = str(PROJECT_ROOT / "packaging")
        if packaging not in sys.path:
            sys.path.insert(0, packaging)
        from verify_linuxdeploy import (  # noqa: WPS433
            ensure_linuxdeploy,
            expected_sha256,
            expected_url,
        )

        return ensure_linuxdeploy, expected_sha256, expected_url

    def test_i_real_pin_loads_official_url_and_full_sha(self) -> None:
        _ensure, expected_sha256, expected_url = self._load_helpers()
        digest = expected_sha256(PIN_FILE)
        url = expected_url(PIN_FILE)
        self.assertEqual(
            url,
            "https://github.com/linuxdeploy/linuxdeploy/releases/download/"
            "continuous/linuxdeploy-x86_64.AppImage",
        )
        self.assertEqual(len(digest), 64)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(
            digest,
            "8aea8da0f7f7039d2a2cecb14657d752a222a5e1d3825caeef186c82f751cdd1",
        )

    def test_j_existing_file_with_wrong_sha_is_rejected(self) -> None:
        ensure_linuxdeploy, _sha, _url = self._load_helpers()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "linuxdeploy-x86_64.AppImage"
            target.write_bytes(b"local-wrong")
            expected = hashlib.sha256(b"official").hexdigest()
            pin = Path(tmp) / "linuxdeploy.pin"
            pin.write_text(
                "LINUXDEPLOY_URL=https://example.invalid/linuxdeploy-x86_64.AppImage\n"
                f"LINUXDEPLOY_SHA256={expected}\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as caught:
                ensure_linuxdeploy(target, pin_path=pin, downloader=self.fail)
            message = str(caught.exception)
            self.assertIn("nebude použit", message)
            self.assertIn(expected, message)
            self.assertIn(hashlib.sha256(b"local-wrong").hexdigest(), message)
            self.assertEqual(target.read_bytes(), b"local-wrong")

    def test_k_missing_file_is_downloaded_and_verified(self) -> None:
        ensure_linuxdeploy, _sha, _url = self._load_helpers()
        payload = b"official-linuxdeploy"
        expected = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "linuxdeploy-x86_64.AppImage"
            pin = Path(tmp) / "linuxdeploy.pin"
            url = "https://example.invalid/linuxdeploy-x86_64.AppImage"
            pin.write_text(
                f"LINUXDEPLOY_URL={url}\nLINUXDEPLOY_SHA256={expected}\n",
                encoding="utf-8",
            )

            def downloader(requested_url: str, destination: Path) -> None:
                self.assertEqual(requested_url, url)
                destination.write_bytes(payload)

            ensure_linuxdeploy(target, pin_path=pin, downloader=downloader)
            self.assertEqual(target.read_bytes(), payload)
            self.assertTrue(target.stat().st_mode & 0o111)

    def test_l_failed_download_and_bad_payload_are_rejected(self) -> None:
        ensure_linuxdeploy, _sha, _url = self._load_helpers()
        expected = hashlib.sha256(b"official").hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pin = root / "linuxdeploy.pin"
            pin.write_text(
                "LINUXDEPLOY_URL=https://example.invalid/linuxdeploy-x86_64.AppImage\n"
                f"LINUXDEPLOY_SHA256={expected}\n",
                encoding="utf-8",
            )
            missing = root / "missing.AppImage"

            def fail_download(_url: str, _destination: Path) -> None:
                raise OSError("síť nedostupná")

            with self.assertRaises(ValueError) as failed:
                ensure_linuxdeploy(missing, pin_path=pin, downloader=fail_download)
            self.assertIn("Stažení linuxdeploy selhalo", str(failed.exception))
            self.assertFalse(missing.exists())
            self.assertFalse(Path(str(missing) + ".partial").exists())

            bad_target = root / "bad.AppImage"

            def bad_payload(_url: str, destination: Path) -> None:
                destination.write_bytes(b"tampered")

            with self.assertRaises(ValueError) as mismatched:
                ensure_linuxdeploy(bad_target, pin_path=pin, downloader=bad_payload)
            message = str(mismatched.exception)
            self.assertIn("staženého linuxdeploy", message)
            self.assertIn(expected, message)
            self.assertIn(hashlib.sha256(b"tampered").hexdigest(), message)
            self.assertFalse(bad_target.exists())
            self.assertFalse(Path(str(bad_target) + ".partial").exists())


if __name__ == "__main__":
    unittest.main()
