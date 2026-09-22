"""Testy pomocného skriptu pro automatické zvýšení patch verze."""

from __future__ import annotations

import io
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import date
from pathlib import Path
from unittest.mock import patch

import tools.release_version as release_module
from tools.release_version import (
    ReleaseVersionError,
    next_patch_version,
    prepare_release,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SKELETON_FILES = (
    "core/version.py",
    "README.md",
    "CHANGELOG.md",
    "generate_version_info.py",
    "generate_installer_iss.py",
    "version_info.txt",
    "installer.iss",
)
TRACKED_RELATIVE_PATHS = (
    "core/version.py",
    "README.md",
    "CHANGELOG.md",
    "version_info.txt",
    "installer.iss",
)
RELEASE_DATE = date(2026, 9, 15)
RELEASE_DESCRIPTION = "Úprava Kontrol změn RPP"
APP_VERSION_ASSIGNMENT = re.compile(
    r'^APP_VERSION = "([^"]*)"$',
    re.MULTILINE,
)
CHANGELOG_VERSION_HEADING = re.compile(
    r"^# Verze (\d+\.\d+\.\d+)$",
    re.MULTILINE,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_copy_app_version(source: str) -> str:
    match = APP_VERSION_ASSIGNMENT.search(source)
    if match is None:
        raise AssertionError("V kopii core/version.py chybí APP_VERSION.")
    return match.group(1)


def _version_tuple(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def _drop_newer_changelog_sections(changelog: str, current: str) -> str:
    """Nechá v CHANGELOG jen sekce aktuální a starší, aby helper mohl přidat další patch."""
    matches = list(CHANGELOG_VERSION_HEADING.finditer(changelog))
    if not matches:
        return changelog
    limit = _version_tuple(current)
    parts = [changelog[: matches[0].start()]]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(changelog)
        if _version_tuple(match.group(1)) <= limit:
            parts.append(changelog[match.start() : end])
    return "".join(parts)


def _snapshot_files(root: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for relative in TRACKED_RELATIVE_PATHS:
        path = root / relative
        if path.exists():
            snapshot[relative] = path.read_bytes()
    return snapshot


def _seed_project(destination: Path) -> Path:
    (destination / "core").mkdir(parents=True, exist_ok=True)
    (destination / "core" / "__init__.py").write_text("", encoding="utf-8")
    for relative in SKELETON_FILES:
        source = REPO_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return destination


class ReleaseHelper2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._live_snapshot = _snapshot_files(REPO_ROOT)

    def setUp(self) -> None:
        self.work_dir = Path(tempfile.mkdtemp(prefix="release-helper-2-"))
        self.project = _seed_project(self.work_dir)
        self.original = _snapshot_files(self.project)

    def tearDown(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)

    @classmethod
    def tearDownClass(cls) -> None:
        live = _snapshot_files(REPO_ROOT)
        if live != cls._live_snapshot:
            raise AssertionError(
                "Testy RELEASE-HELPER-2 nesmí měnit aktuální verzi v pracovním stromu."
            )

    def _set_current_version(self, version: str) -> None:
        version_path = self.project / "core" / "version.py"
        source = re.sub(
            r'^APP_VERSION = "[^"]*"',
            f'APP_VERSION = "{version}"',
            _read(version_path),
            count=1,
            flags=re.MULTILINE,
        )
        version_path.write_text(source, encoding="utf-8")
        readme_path = self.project / "README.md"
        readme = re.sub(
            r"^# Manažer BOZP \d+\.\d+\.\d+",
            f"# Manažer BOZP {version}",
            _read(readme_path),
            count=1,
            flags=re.MULTILINE,
        )
        readme_path.write_text(readme, encoding="utf-8")
        changelog_path = self.project / "CHANGELOG.md"
        changelog_path.write_text(
            _drop_newer_changelog_sections(_read(changelog_path), version),
            encoding="utf-8",
        )
        self.original = _snapshot_files(self.project)

    def _copy_current_and_next(self) -> tuple[str, str]:
        current = _parse_copy_app_version(_read(self.project / "core" / "version.py"))
        return current, next_patch_version(current)

    def _prepare(self, description: str = RELEASE_DESCRIPTION):
        return prepare_release(
            description,
            project_root=self.project,
            today=RELEASE_DATE,
        )

    def _assert_released(self, version: str, description: str) -> None:
        major, minor, patch = version.split(".")
        source = _read(self.project / "core" / "version.py")
        self.assertIn(f'APP_VERSION = "{version}"', source)
        self.assertEqual(source.count("APP_VERSION = "), 1)
        self.assertTrue(
            _read(self.project / "README.md").startswith(f"# Manažer BOZP {version}")
        )
        changelog = _read(self.project / "CHANGELOG.md")
        self.assertIn(f"# Verze {version}", changelog)
        self.assertIn("Datum vydání:", changelog)
        self.assertIn("15. 9. 2026", changelog)
        self.assertIn(description, changelog)
        info = _read(self.project / "version_info.txt")
        self.assertIn(f"filevers=({major}, {minor}, {patch}, 0)", info)
        self.assertIn(f"prodvers=({major}, {minor}, {patch}, 0)", info)
        self.assertIn(f"StringStruct('FileVersion', '{version}')", info)
        self.assertIn(f"StringStruct('ProductVersion', '{version}')", info)
        installer = _read(self.project / "installer.iss")
        self.assertIn(f'#define MyAppVersion "{version}"', installer)
        self.assertIn(
            f"OutputBaseFilename=Manazer_BOZP_{version.replace('.', '_')}_Setup",
            installer,
        )

    def test_bumps_4_0_1_to_4_0_2(self) -> None:
        self._set_current_version("4.0.1")
        self.assertNotIn("# Verze 4.0.2", _read(self.project / "CHANGELOG.md"))
        result = self._prepare()
        self.assertEqual(result.old_version, "4.0.1")
        self.assertEqual(result.new_version, "4.0.2")
        self.assertTrue(result.changelog_added)
        self._assert_released("4.0.2", RELEASE_DESCRIPTION)
        changelog = _read(self.project / "CHANGELOG.md")
        self.assertIn("# Verze 4.0.1", changelog)
        self.assertLess(changelog.index("# Verze 4.0.2"), changelog.index("# Verze 4.0.1"))

    def test_bumps_4_0_9_to_4_0_10(self) -> None:
        self._set_current_version("4.0.9")
        result = self._prepare("Oprava exportu plánu auditů")
        self.assertEqual(result.old_version, "4.0.9")
        self.assertEqual(result.new_version, "4.0.10")
        self._assert_released("4.0.10", "Oprava exportu plánu auditů")

    def test_bumps_4_2_99_to_4_2_100(self) -> None:
        self._set_current_version("4.2.99")
        result = self._prepare("Oprava zobrazení programu externího auditu")
        self.assertEqual(result.old_version, "4.2.99")
        self.assertEqual(result.new_version, "4.2.100")
        self._assert_released("4.2.100", "Oprava zobrazení programu externího auditu")

    def test_automatic_bump_keeps_major_and_minor(self) -> None:
        self.assertEqual(next_patch_version("4.0.1"), "4.0.2")
        self.assertEqual(next_patch_version("4.0.9"), "4.0.10")
        self.assertEqual(next_patch_version("4.2.99"), "4.2.100")
        for current in ("4.0.1", "4.0.9", "4.2.99"):
            old_major, old_minor, _old_patch = current.split(".")
            new_major, new_minor, _new_patch = next_patch_version(current).split(".")
            self.assertEqual(new_major, old_major)
            self.assertEqual(new_minor, old_minor)

        old_version, new_version = self._copy_current_and_next()
        result = self._prepare()
        self.assertEqual(result.old_version, old_version)
        self.assertEqual(result.new_version, new_version)
        old_major, old_minor, old_patch = old_version.split(".")
        new_major, new_minor, new_patch = new_version.split(".")
        self.assertEqual(new_major, old_major)
        self.assertEqual(new_minor, old_minor)
        self.assertEqual(int(new_patch), int(old_patch) + 1)

    def test_generated_files_contain_computed_version(self) -> None:
        old_version, new_version = self._copy_current_and_next()
        result = self._prepare()
        self.assertEqual(result.old_version, old_version)
        self.assertEqual(result.new_version, new_version)
        self._assert_released(new_version, RELEASE_DESCRIPTION)
        changelog = _read(self.project / "CHANGELOG.md")
        self.assertIn("# Verze 4.0.0", changelog)
        self.assertIn("Manažer BOZP 4.0.1", changelog)
        self.assertIn(f"# Verze {old_version}", changelog)
        self.assertLess(
            changelog.index(f"# Verze {new_version}"),
            changelog.index(f"# Verze {old_version}"),
        )

    def test_error_during_operation_restores_files(self) -> None:
        (self.project / "generate_version_info.py").write_text(
            'raise SystemExit("simulovaná chyba generátoru")\n',
            encoding="utf-8",
        )
        with self.assertRaises(ReleaseVersionError) as caught:
            self._prepare()
        self.assertIn("generate_version_info.py", str(caught.exception))
        self.assertEqual(_snapshot_files(self.project), self.original)

    def test_missing_description_does_not_change_files(self) -> None:
        for description in ("", "   "):
            with self.subTest(description=repr(description)):
                with self.assertRaises(ReleaseVersionError):
                    self._prepare(description=description)
                self.assertEqual(_snapshot_files(self.project), self.original)

        parser = release_module.build_parser()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args([])
            with self.assertRaises(SystemExit):
                parser.parse_args(["4.0.2", "popis změny"])
        self.assertEqual(_snapshot_files(self.project), self.original)

    def test_helper_does_not_commit_tag_or_build(self) -> None:
        source = Path(release_module.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "git commit",
            "git tag",
            "git push",
            "build_release",
            "build_old_release",
            "appimagetool",
            "AppDir",
            "iscc",
        ):
            self.assertNotIn(forbidden, source)
        self.assertNotIn('["git"', source)
        self.assertNotIn("'git'", source)
        self.assertEqual(
            list(release_module.GENERATOR_SCRIPTS),
            ["generate_version_info.py", "generate_installer_iss.py"],
        )

        recorded: list[list[str]] = []
        original_run = release_module.subprocess.run

        def _tracking_run(command, *args, **kwargs):
            recorded.append(list(command))
            return original_run(command, *args, **kwargs)

        with patch.object(release_module.subprocess, "run", side_effect=_tracking_run):
            self._prepare()

        self.assertEqual(len(recorded), 2)
        for command in recorded:
            self.assertEqual(command[0], release_module.sys.executable)
            self.assertTrue(
                command[1].endswith("generate_version_info.py")
                or command[1].endswith("generate_installer_iss.py")
            )
            self.assertFalse(any(part == "git" for part in command))


if __name__ == "__main__":
    unittest.main()
