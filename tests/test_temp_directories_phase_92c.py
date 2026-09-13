import re
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TempDirectoryPolicyPhase92cTestCase(unittest.TestCase):
    def test_attachment_backup_env_uses_system_temp_with_cleanup(self) -> None:
        content = (PROJECT_ROOT / "tests/attachment_backup_test_env.py").read_text(encoding="utf-8")
        self.assertNotIn("mkdtemp(dir=_PROJECT_ROOT)", content)
        self.assertIn("create_tracked_temp_dir", content)

    def test_attachment_tests_do_not_use_project_root_temp(self) -> None:
        for name in ("test_attachment_backup_phase_92a.py", "test_attachment_backup_phase_92b.py"):
            content = (PROJECT_ROOT / "tests" / name).read_text(encoding="utf-8")
            self.assertNotIn("mkdtemp(dir=_PROJECT_ROOT)", content)
            self.assertIn("TemporaryDirectory", content)

    def test_build_release_uses_system_temp_for_linuxdeploy(self) -> None:
        content = (PROJECT_ROOT / "build_release.sh").read_text(encoding="utf-8")
        self.assertIn("mktemp -d", content)
        self.assertIn("LINUXDEPLOY_WORKDIR", content)
        self.assertIn('trap cleanup_linuxdeploy_workdir EXIT', content)
        self.assertNotIn("./squashfs-root/AppRun", content)

    def test_build_old_release_uses_system_temp_and_cleans_squashfs(self) -> None:
        content = (PROJECT_ROOT / "build_old_release.sh").read_text(encoding="utf-8")
        self.assertIn("mktemp -d", content)
        self.assertIn('rm -rf "$LINUXDEPLOY_WORKDIR" /src/squashfs-root', content)
        self.assertNotIn('./linuxdeploy-x86_64.AppImage --appimage-extract', content)

    def test_tracked_temp_dir_is_created_in_system_temp(self) -> None:
        from tests.temp_dir_helpers import create_tracked_temp_dir

        path = create_tracked_temp_dir()
        self.assertTrue(path.is_dir())
        self.assertTrue(str(path).startswith(tempfile.gettempdir()))
        self.assertFalse(path.is_relative_to(PROJECT_ROOT))

    def test_backup_restore_uses_system_temp_for_extract(self) -> None:
        content = (PROJECT_ROOT / "core/backup/package_restore.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("tempfile.mkdtemp", content)
        self.assertIn("mbrestore-extract-", content)

    def test_open_export_uses_system_tempdir(self) -> None:
        content = (PROJECT_ROOT / "core/export/open_export.py").read_text(encoding="utf-8")
        self.assertIn("tempfile.gettempdir()", content)
        self.assertNotRegex(content, r'mkdtemp\([^)]*dir\s*=')


if __name__ == "__main__":
    unittest.main()
