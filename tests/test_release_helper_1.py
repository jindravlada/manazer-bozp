"""Testy pomocného skriptu pro přípravu nové verze aplikace."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import tools.release_version as release_module
from tools.release_version import ReleaseVersionError, prepare_release

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
RELEASE_DESCRIPTION = "Opravy exportu auditů a RPP"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


class ReleaseHelper1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._live_snapshot = _snapshot_files(REPO_ROOT)

    def setUp(self) -> None:
        self.work_dir = Path(tempfile.mkdtemp(prefix="release-helper-1-"))
        self.project = _seed_project(self.work_dir)
        self.original = _snapshot_files(self.project)

    def tearDown(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)

    @classmethod
    def tearDownClass(cls) -> None:
        live = _snapshot_files(REPO_ROOT)
        if live != cls._live_snapshot:
            raise AssertionError(
                "Testy RELEASE-HELPER-1 nesmí měnit aktuální verzi v pracovním stromu."
            )

    def _prepare(self, version: str = "4.0.2", description: str = RELEASE_DESCRIPTION):
        return prepare_release(
            version,
            description,
            project_root=self.project,
            today=RELEASE_DATE,
        )

    def test_bumps_4_0_1_to_4_0_2(self) -> None:
        result = self._prepare()
        self.assertEqual(result.old_version, "4.0.1")
        self.assertEqual(result.new_version, "4.0.2")
        self.assertTrue(result.changelog_added)

    def test_app_version_is_updated(self) -> None:
        self._prepare()
        source = _read(self.project / "core" / "version.py")
        self.assertIn('APP_VERSION = "4.0.2"', source)
        self.assertNotIn('APP_VERSION = "4.0.1"', source)
        self.assertEqual(source.count("APP_VERSION = "), 1)

    def test_readme_contains_new_version(self) -> None:
        self._prepare()
        readme = _read(self.project / "README.md")
        self.assertTrue(readme.startswith("# Manažer BOZP 4.0.2"))
        self.assertFalse(readme.startswith("# Manažer BOZP 4.0.1"))

    def test_changelog_adds_section_and_keeps_history(self) -> None:
        changelog_before = _read(self.project / "CHANGELOG.md")
        self._prepare()
        changelog = _read(self.project / "CHANGELOG.md")
        self.assertIn("# Verze 4.0.2", changelog)
        self.assertIn("15. 9. 2026", changelog)
        self.assertIn(RELEASE_DESCRIPTION, changelog)
        self.assertIn("# Verze 4.0.1", changelog)
        self.assertIn("# Verze 4.0.0", changelog)
        self.assertIn("Manažer BOZP 4.0.1", changelog)
        self.assertEqual(changelog.count("# Verze 4.0.1"), changelog_before.count("# Verze 4.0.1"))
        self.assertEqual(changelog.count("# Verze 4.0.0"), changelog_before.count("# Verze 4.0.0"))
        self.assertLess(
            changelog.index("# Verze 4.0.2"),
            changelog.index("# Verze 4.0.1"),
        )

    def test_version_info_matches_new_version(self) -> None:
        self._prepare()
        content = _read(self.project / "version_info.txt")
        self.assertIn("filevers=(4, 0, 2, 0)", content)
        self.assertIn("prodvers=(4, 0, 2, 0)", content)
        self.assertIn("StringStruct('FileVersion', '4.0.2')", content)
        self.assertIn("StringStruct('ProductVersion', '4.0.2')", content)
        self.assertNotIn("StringStruct('FileVersion', '4.0.1')", content)

    def test_installer_iss_matches_new_version(self) -> None:
        self._prepare()
        content = _read(self.project / "installer.iss")
        self.assertIn('#define MyAppVersion "4.0.2"', content)
        self.assertIn("OutputBaseFilename=Manazer_BOZP_4_0_2_Setup", content)
        self.assertNotIn('#define MyAppVersion "4.0.1"', content)
        self.assertNotIn("Manazer_BOZP_4_0_1_Setup", content)

    def test_invalid_version_does_not_change_files(self) -> None:
        for invalid in ("4.0", "abc", "4.0.2-beta", "v4.0.2"):
            with self.subTest(version=invalid):
                with self.assertRaises(ReleaseVersionError):
                    self._prepare(version=invalid)
                self.assertEqual(_snapshot_files(self.project), self.original)

    def test_error_during_operation_restores_files(self) -> None:
        (self.project / "generate_version_info.py").write_text(
            'raise SystemExit("simulovaná chyba generátoru")\n',
            encoding="utf-8",
        )
        with self.assertRaises(ReleaseVersionError) as caught:
            self._prepare()
        self.assertIn("generate_version_info.py", str(caught.exception))
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
            self.assertTrue(command[1].endswith("generate_version_info.py") or command[1].endswith("generate_installer_iss.py"))
            self.assertFalse(any(part == "git" for part in command))

    def test_same_version_does_not_duplicate_changelog_section(self) -> None:
        first = self._prepare()
        self.assertTrue(first.changelog_added)
        changelog_after_first = _read(self.project / "CHANGELOG.md")
        second = self._prepare()
        self.assertFalse(second.changelog_added)
        changelog_after_second = _read(self.project / "CHANGELOG.md")
        self.assertEqual(changelog_after_first.count("# Verze 4.0.2"), 1)
        self.assertEqual(changelog_after_second, changelog_after_first)
        self.assertIn('APP_VERSION = "4.0.2"', _read(self.project / "core" / "version.py"))


if __name__ == "__main__":
    unittest.main()
