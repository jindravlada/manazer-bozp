"""SEC-HARDENING-DATA-2: úklid dočasných auditních preview souborů."""

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
    create_managed_temp_file,
    is_open_export_temp_name,
    unlink_managed_temp_file,
)
from moduly.audity.sluzby.audit_program_plan_export_service import (
    audit_program_plan_export_service,
)
from moduly.audity.sluzby.audit_program_statements_export_service import (
    audit_program_statements_export_service,
)

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "sec-hardening-data-2"


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


class SecHardeningData2TestCase(unittest.TestCase):
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

    def _write_target(self, _ident: int, target):
        path = Path(target)
        path.write_bytes(b"PK\x03\x04-preview")
        return path

    def test_a_preview_temp_has_mode_0600(self) -> None:
        path = create_managed_temp_file(name_hint="Plan_internich_auditu_x.odt")
        self.assertTrue(path.is_file())
        self.assertEqual(_mode(path), 0o600)
        self.assertTrue(is_open_export_temp_name(path.name))
        self.assertIn("Plan_internich_auditu_x.odt", path.name)

        with patch.object(
            audit_program_plan_export_service,
            "default_filename",
            return_value="Plan_internich_auditu_test.odt",
        ), patch.object(
            audit_program_plan_export_service,
            "generate_for_program",
            side_effect=self._write_target,
        ):
            preview = audit_program_plan_export_service.generate_preview_for_program(1)
        self.assertEqual(_mode(preview), 0o600)
        self.assertEqual(preview.read_bytes(), b"PK\x03\x04-preview")
        self.assertTrue(is_open_export_temp_name(preview.name))

    def test_b_preview_path_can_be_passed_to_opener(self) -> None:
        with patch.object(
            audit_program_plan_export_service,
            "default_filename",
            return_value="Plan_internich_auditu_open.odt",
        ), patch.object(
            audit_program_plan_export_service,
            "generate_for_program",
            side_effect=self._write_target,
        ):
            preview = audit_program_plan_export_service.generate_preview_for_program(7)
        with patch(
            "core.export.open_export._open_with_gio", return_value=True
        ) as mock_gio, patch(
            "core.export.open_export._is_appimage", return_value=False
        ), patch(
            "core.export.open_export._open_with_xdg_open", return_value=True
        ) as mock_xdg:
            from core.export.open_export import open_local_file

            opened = open_local_file(preview, show_error=False)
        self.assertTrue(opened)
        mock_xdg.assert_called_once()
        mock_gio.assert_not_called()
        self.assertTrue(preview.exists())

    def test_c_tracked_cleanup_removes_preview(self) -> None:
        with patch.object(
            audit_program_statements_export_service,
            "default_filename",
            return_value="Auditni_tvrzeni_test.odt",
        ), patch.object(
            audit_program_statements_export_service,
            "_render",
            side_effect=lambda _ctx, target: self._write_target(0, target),
        ), patch(
            "moduly.audity.sluzby.audit_program_statements_export_service."
            "audit_program_statements_export_context_service.build_for_visit",
            return_value=object(),
        ):
            preview = audit_program_statements_export_service.generate_preview_for_visit(3)
        self.assertTrue(preview.exists())
        cleanup_tracked_open_export_temps()
        self.assertFalse(preview.exists())

        orphan = self.temp_dir / f"manazer-bozp-{uuid.uuid4().hex}-Plan_internich_auditu.odt"
        orphan.write_bytes(b"orphan-preview")
        cleanup_orphan_open_export_temps()
        self.assertFalse(orphan.exists())

    def test_d_foreign_temp_file_is_untouched(self) -> None:
        foreign = self.temp_dir / "cizi-preview.odt"
        foreign.write_bytes(b"keep")
        similar = self.temp_dir / "Plan_internich_auditu_legacy.odt"
        similar.write_bytes(b"old-prefix")
        cleanup_orphan_open_export_temps()
        self.assertTrue(foreign.exists())
        self.assertTrue(similar.exists())

    def test_e_symlink_is_not_followed(self) -> None:
        canary = self.work / "CANARY.odt"
        canary.write_bytes(b"keep-target")
        link = self.temp_dir / f"manazer-bozp-{uuid.uuid4().hex}-evil.odt"
        os.symlink(canary, link)
        cleanup_orphan_open_export_temps()
        self.assertTrue(canary.exists())
        self.assertEqual(canary.read_bytes(), b"keep-target")
        self.assertTrue(link.is_symlink())

    def test_f_cleanup_error_does_not_raise(self) -> None:
        path = create_managed_temp_file(name_hint="x.odt")
        with patch("core.export.open_export.os.unlink", side_effect=OSError("denied")):
            cleanup_tracked_open_export_temps()
            cleanup_orphan_open_export_temps()
            unlink_managed_temp_file(path)
        self.assertTrue(path.exists())

    def test_failed_generate_unlinks_temp(self) -> None:
        with patch.object(
            audit_program_plan_export_service,
            "default_filename",
            return_value="Plan_internich_auditu_fail.odt",
        ), patch.object(
            audit_program_plan_export_service,
            "generate_for_program",
            side_effect=RuntimeError("render selhal"),
        ):
            with self.assertRaises(RuntimeError):
                audit_program_plan_export_service.generate_preview_for_program(1)
        leftover = [path for path in self.temp_dir.iterdir() if path.is_file()]
        self.assertEqual(leftover, [])


if __name__ == "__main__":
    unittest.main()
