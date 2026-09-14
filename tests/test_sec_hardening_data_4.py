"""SEC-HARDENING-DATA-4: kořen workspace na POSIX jen pro vlastníka (0700)."""

from __future__ import annotations

import os
import shutil
import stat
import unittest
from pathlib import Path
from unittest.mock import patch

from core.services.storage_service import (
    StorageService,
    _WORKSPACE_DIR_MODE,
    ensure_private_workspace_root,
)

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "sec-hardening-data-4"


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


class SecHardeningData4TestCase(unittest.TestCase):
    def setUp(self) -> None:
        if _TEST_ROOT.exists():
            shutil.rmtree(_TEST_ROOT)
        self.work = _TEST_ROOT / "work"
        self.work.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(_TEST_ROOT, ignore_errors=True)

    def _ws(self, name: str = "manazer-bozp") -> Path:
        path = self.work / name
        path.mkdir()
        return path

    def _ensure_structure_on(self, base: Path) -> None:
        service = StorageService.__new__(StorageService)
        service.base = base
        with patch.object(StorageService, "ensure_default_templates"), patch.object(
            StorageService, "ensure_editable_catalogs"
        ):
            service.ensure_structure()

    def test_a_new_workspace_root_is_0700(self) -> None:
        base = self.work / "new-ws"
        self.assertFalse(base.exists())
        self._ensure_structure_on(base)
        self.assertTrue(base.is_dir())
        self.assertFalse(base.is_symlink())
        self.assertEqual(_mode(base), 0o700)

    def test_b_existing_0755_owned_root_becomes_0700(self) -> None:
        base = self._ws("old-ws")
        os.chmod(base, 0o755)
        self.assertEqual(_mode(base), 0o755)
        ensure_private_workspace_root(base)
        self.assertEqual(_mode(base), 0o700)

    def test_c_existing_0700_is_unchanged(self) -> None:
        base = self._ws("already-private")
        os.chmod(base, 0o700)
        with patch("core.services.storage_service.os.chmod") as mock_chmod:
            ensure_private_workspace_root(base)
        mock_chmod.assert_not_called()
        self.assertEqual(_mode(base), 0o700)

    def test_d_no_recursive_chmod(self) -> None:
        base = self._ws("nested")
        os.chmod(base, 0o755)
        child_dir = base / "databaze"
        child_dir.mkdir()
        os.chmod(child_dir, 0o755)
        child_file = child_dir / "manager_bozp.db"
        child_file.write_bytes(b"sqlite")
        os.chmod(child_file, 0o644)
        ensure_private_workspace_root(base)
        self.assertEqual(_mode(base), 0o700)
        self.assertEqual(_mode(child_dir), 0o755)
        self.assertEqual(_mode(child_file), 0o644)

    def test_e_path_outside_workspace_is_untouched(self) -> None:
        outside = self.work / "mimo-workspace"
        outside.mkdir()
        os.chmod(outside, 0o755)
        marker = outside / "KEEP.txt"
        marker.write_text("keep", encoding="utf-8")
        os.chmod(marker, 0o644)
        base = self._ws("ws")
        os.chmod(base, 0o755)
        ensure_private_workspace_root(base)
        self.assertEqual(_mode(outside), 0o755)
        self.assertTrue(marker.exists())
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        self.assertEqual(_mode(marker), 0o644)

    def test_f_chmod_failure_does_not_destroy_data(self) -> None:
        base = self._ws("fail-ws")
        os.chmod(base, 0o755)
        canary = base / "CANARY.db"
        canary.write_bytes(b"payload")
        with patch(
            "core.services.storage_service.os.chmod",
            side_effect=OSError("denied"),
        ):
            ensure_private_workspace_root(base)
        self.assertTrue(base.is_dir())
        self.assertTrue(canary.exists())
        self.assertEqual(canary.read_bytes(), b"payload")

    def test_g_windows_does_not_posix_chmod(self) -> None:
        base = self._ws("win-ws")
        os.chmod(base, 0o755)
        with patch(
            "core.services.storage_service.platform.system",
            return_value="Windows",
        ), patch("core.services.storage_service.os.chmod") as mock_chmod:
            ensure_private_workspace_root(base)
        mock_chmod.assert_not_called()
        self.assertEqual(_mode(base), 0o755)

    def test_symlink_root_is_not_followed(self) -> None:
        real = self.work / "real-target"
        real.mkdir()
        os.chmod(real, 0o755)
        canary = real / "KEEP.txt"
        canary.write_text("target", encoding="utf-8")
        link = self.work / "symlink-ws"
        os.symlink(real, link)
        ensure_private_workspace_root(link)
        self.assertTrue(link.is_symlink())
        self.assertEqual(_mode(real), 0o755)
        self.assertEqual(canary.read_text(encoding="utf-8"), "target")

    def test_foreign_owner_is_not_chmodded(self) -> None:
        base = self._ws("foreign")
        os.chmod(base, 0o755)
        real = os.lstat(base)

        class _ForeignStat:
            st_mode = real.st_mode
            st_uid = real.st_uid + 1

        with patch(
            "core.services.storage_service.os.lstat",
            return_value=_ForeignStat(),
        ), patch("core.services.storage_service.os.chmod") as mock_chmod:
            ensure_private_workspace_root(base)
        mock_chmod.assert_not_called()
        self.assertEqual(_mode(base), 0o755)

    def test_workspace_mode_constant_is_0700(self) -> None:
        self.assertEqual(_WORKSPACE_DIR_MODE, 0o700)


if __name__ == "__main__":
    unittest.main()
