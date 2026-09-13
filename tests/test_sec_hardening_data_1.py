"""SEC-HARDENING-DATA-1: soukromé a uklízené AppImage temp kopie."""

from __future__ import annotations

import os
import shutil
import stat
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from core.export import open_export as open_export_module
from core.export.open_export import (
    cleanup_orphan_open_export_temps,
    cleanup_tracked_open_export_temps,
    create_open_export_temp_copy,
    is_open_export_temp_name,
    _open_via_private_temp_copy,
)

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "sec-hardening-data-1"


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


class SecHardeningData1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        if _TEST_ROOT.exists():
            shutil.rmtree(_TEST_ROOT)
        self.temp_dir = _TEST_ROOT / "tmp"
        self.work = _TEST_ROOT / "work"
        self.temp_dir.mkdir(parents=True)
        self.work.mkdir(parents=True)
        self._gettempdir = patch(
            "core.export.open_export.tempfile.gettempdir",
            return_value=str(self.temp_dir),
        )
        self._gettempdir.start()
        self.addCleanup(self._gettempdir.stop)
        open_export_module._created_temp_copies.clear()

    def tearDown(self) -> None:
        open_export_module._created_temp_copies.clear()
        shutil.rmtree(_TEST_ROOT, ignore_errors=True)

    def _source(self, name: str = "protokol.odt", payload: bytes = b"PK-DATA-1") -> Path:
        path = self.work / name
        path.write_bytes(payload)
        return path

    def _orphan_name(self, suffix: str = "dokument.pdf") -> str:
        return f"manazer-bozp-{uuid.uuid4().hex}-{suffix}"

    def test_a_temp_copy_mode_is_0600(self) -> None:
        source = self._source()
        copied = create_open_export_temp_copy(source)
        self.assertIsNotNone(copied)
        assert copied is not None
        self.assertTrue(copied.is_file())
        self.assertEqual(_mode(copied), 0o600)
        self.assertTrue(is_open_export_temp_name(copied.name))
        self.assertTrue(copied.is_relative_to(self.temp_dir))

    def test_b_temp_copy_matches_source_bytes(self) -> None:
        payload = b"%PDF-1.4 personal-bozp"
        source = self._source("priloha.pdf", payload)
        copied = create_open_export_temp_copy(source)
        self.assertIsNotNone(copied)
        assert copied is not None
        self.assertEqual(copied.read_bytes(), payload)
        self.assertEqual(source.read_bytes(), payload)

    def test_c_orphan_cleanup_removes_only_own_temps(self) -> None:
        own = self.temp_dir / self._orphan_name()
        own.write_bytes(b"own-orphan")
        leftover = create_open_export_temp_copy(self._source("dalsi.odt"))
        self.assertIsNotNone(leftover)
        cleanup_orphan_open_export_temps()
        self.assertFalse(own.exists())
        assert leftover is not None
        self.assertFalse(leftover.exists())

    def test_d_foreign_temp_file_is_untouched(self) -> None:
        foreign = self.temp_dir / "cizi-soubor.txt"
        foreign.write_bytes(b"keep-me")
        similar = self.temp_dir / "manazer-bozp-instance-not-this.mbbackup"
        similar.write_bytes(b"backup-name")
        own = self.temp_dir / self._orphan_name("x.pdf")
        own.write_bytes(b"remove")
        cleanup_orphan_open_export_temps()
        self.assertTrue(foreign.exists())
        self.assertEqual(foreign.read_bytes(), b"keep-me")
        self.assertTrue(similar.exists())
        self.assertFalse(own.exists())

    def test_e_symlink_is_not_followed_to_delete_target(self) -> None:
        canary = self.work / "CANARY.txt"
        canary.write_bytes(b"do-not-delete")
        link = self.temp_dir / self._orphan_name("evil.odt")
        os.symlink(canary, link)
        self.assertTrue(link.is_symlink())
        cleanup_orphan_open_export_temps()
        self.assertTrue(canary.exists())
        self.assertEqual(canary.read_bytes(), b"do-not-delete")
        self.assertTrue(link.exists())
        self.assertTrue(link.is_symlink())

    def test_f_cleanup_error_does_not_raise(self) -> None:
        copied = create_open_export_temp_copy(self._source())
        self.assertIsNotNone(copied)
        with patch("core.export.open_export.os.unlink", side_effect=OSError("denied")):
            cleanup_tracked_open_export_temps()
            cleanup_orphan_open_export_temps()
        self.assertTrue(copied.exists())

    def test_tracked_cleanup_removes_current_run_copies(self) -> None:
        copied = create_open_export_temp_copy(self._source("a.pdf", b"abc"))
        self.assertIsNotNone(copied)
        assert copied is not None
        self.assertTrue(copied.exists())
        cleanup_tracked_open_export_temps()
        self.assertFalse(copied.exists())
        self.assertEqual(open_export_module._created_temp_copies, set())

    def test_failed_open_unlinks_temp_copy_immediately(self) -> None:
        source = self._source("fail.pdf", b"payload")
        with patch("core.export.open_export._open_with_gio", return_value=False), patch(
            "core.export.open_export._open_with_system_xdg_open",
            return_value=False,
        ):
            opened = _open_via_private_temp_copy(
                source,
                env={},
                include_office=False,
            )
        self.assertFalse(opened)
        leftover = [path for path in self.temp_dir.iterdir() if path.is_file()]
        self.assertEqual(leftover, [])

    def test_successful_open_keeps_temp_copy_until_cleanup(self) -> None:
        source = self._source("ok.pdf", b"payload-ok")
        with patch("core.export.open_export._open_with_gio", return_value=True):
            opened = _open_via_private_temp_copy(
                source,
                env={},
                include_office=False,
            )
        self.assertTrue(opened)
        copies = [path for path in self.temp_dir.iterdir() if path.is_file()]
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), b"payload-ok")
        self.assertEqual(_mode(copies[0]), 0o600)
        cleanup_tracked_open_export_temps()
        self.assertFalse(copies[0].exists())

    def test_source_file_is_not_modified(self) -> None:
        source = self._source("origin.odt", b"original-bytes")
        before = source.read_bytes()
        copied = create_open_export_temp_copy(source)
        self.assertIsNotNone(copied)
        self.assertEqual(source.read_bytes(), before)

    def test_main_hooks_orphan_cleanup_and_shutdown(self) -> None:
        main_src = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")
        self.assertIn("cleanup_orphan_open_export_temps", main_src)
        self.assertIn("install_open_export_temp_cleanup", main_src)
        export_src = (
            Path(__file__).resolve().parents[1] / "core/export/open_export.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("0o644", export_src)
        self.assertIn("0o600", export_src)


if __name__ == "__main__":
    unittest.main()
