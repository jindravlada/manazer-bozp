"""SEC-05a: cesty příloh a fotografií nesmí opustit své úložiště."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.models.attachment_staging import PreparedAttachmentChanges
from core.services.attachment_service import AttachmentService
from core.services.control_result_photo_service import control_result_photo_service
from core.services.storage_service import storage_service
from core.utils.confined_path import resolve_confined_path
from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
    CoordinationAttachmentError,
    coordination_attachment_service,
)
from moduly.koordinace_bozp.sluzby.coordination_pbp_attachment_service import (
    CoordinationPbpAttachmentError,
    coordination_pbp_attachment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_photo_service import (
    hazard_identification_photo_service,
)


class Sec05aPathConfinementTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sec05a-"))
        self.workspace = self.tmp / "workspace"
        self.outside = self.tmp / "outside"
        self.workspace.mkdir()
        self.outside.mkdir()
        (self.workspace / "prilohy").mkdir()
        (self.workspace / "control_results").mkdir()
        self.sentinel = self.outside / "SENTINEL.txt"
        self.sentinel.write_text("nesmazat", encoding="utf-8")
        self._orig_bases: list[tuple[object, Path]] = []
        for module in list(sys.modules.values()):
            svc = getattr(module, "storage_service", None)
            if svc is None or not hasattr(svc, "base"):
                continue
            if any(item is svc for item, _base in self._orig_bases):
                continue
            self._orig_bases.append((svc, svc.base))
            svc.base = self.workspace
        self.service = AttachmentService()
        self.service.repository.add = self._fake_add

    def tearDown(self) -> None:
        for svc, base in self._orig_bases:
            svc.base = base
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def _fake_add(attachment, *, session=None):
        attachment.id = 1
        return attachment

    def _write_inside(self, relative: str, text: str = "ok") -> Path:
        path = storage_service.attachments_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_helper_rejects_parent_absolute_and_symlink(self) -> None:
        root = storage_service.attachments_dir
        inside = self._write_inside("task/1/doklad.txt")
        self.assertEqual(
            resolve_confined_path(root, "task/1/doklad.txt"),
            inside.resolve(),
        )
        self.assertIsNone(resolve_confined_path(root, "../outside/SENTINEL.txt"))
        self.assertIsNone(resolve_confined_path(root, str(self.sentinel)))
        link = root / "task" / "1" / "odkaz.txt"
        link.symlink_to(self.sentinel)
        self.assertIsNone(resolve_confined_path(root, "task/1/odkaz.txt"))

    def test_ordinary_relative_stored_path_resolves(self) -> None:
        stored = self._write_inside("task/13/protokol.pdf")
        attachment = SimpleNamespace(stored_path="task/13/protokol.pdf")
        resolved = self.service.resolve_path(attachment)
        self.assertEqual(resolved, stored.resolve())
        self.assertTrue(resolved.is_file())

    def test_parent_escape_stored_path_is_rejected(self) -> None:
        attachment = SimpleNamespace(stored_path="../outside/SENTINEL.txt")
        with self.assertRaises(ValueError) as ctx:
            self.service.resolve_path(attachment)
        self.assertIn("prilohy", str(ctx.exception))
        self.assertTrue(self.sentinel.is_file())

    def test_absolute_stored_path_is_rejected(self) -> None:
        attachment = SimpleNamespace(stored_path=str(self.sentinel))
        with self.assertRaises(ValueError):
            self.service.resolve_path(attachment)
        self.assertTrue(self.sentinel.is_file())

    def test_symlink_out_of_prilohy_is_rejected(self) -> None:
        link = storage_service.attachments_dir / "task" / "1" / "link.txt"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(self.sentinel)
        attachment = SimpleNamespace(stored_path="task/1/link.txt")
        with self.assertRaises(ValueError):
            self.service.resolve_path(attachment)
        self.assertTrue(self.sentinel.is_file())

    def test_finalize_does_not_unlink_outside_sentinel(self) -> None:
        prepared = PreparedAttachmentChanges(
            entity_type="task",
            entity_id=1,
            pending_unlink_paths=[self.sentinel],
        )
        warnings = self.service.finalize_attachment_changes(prepared)
        self.assertTrue(self.sentinel.is_file())
        self.assertTrue(any("prilohy" in item for item in warnings))

    def test_finalize_does_not_follow_symlink_to_sentinel(self) -> None:
        link = storage_service.attachments_dir / "task" / "2" / "link.txt"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(self.sentinel)
        prepared = PreparedAttachmentChanges(
            entity_type="task",
            entity_id=2,
            pending_unlink_paths=[link],
        )
        self.service.finalize_attachment_changes(prepared)
        self.assertTrue(self.sentinel.is_file())

    def test_poisoned_db_remove_does_not_delete_outside_file(self) -> None:
        """pending_unlink z resolve_confined_path(None) se do seznamu nedostane."""
        record = SimpleNamespace(
            id=99,
            entity_type="task",
            entity_id=3,
            stored_path=str(self.sentinel),
        )
        confined = resolve_confined_path(
            storage_service.attachments_dir, record.stored_path
        )
        self.assertIsNone(confined)
        pending: list[Path] = []
        if confined is not None:
            pending.append(confined)
        prepared = PreparedAttachmentChanges(
            entity_type="task",
            entity_id=3,
            pending_unlink_paths=pending,
        )
        self.service.finalize_attachment_changes(prepared)
        self.assertTrue(self.sentinel.is_file())

    def test_control_result_ordinary_photo_path(self) -> None:
        relative = "control_results/audity/8/sekce_bod_photo.jpg"
        target = control_result_photo_service.absolute_photo_path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("foto", encoding="utf-8")
        resolved = control_result_photo_service.absolute_photo_path(relative)
        self.assertEqual(resolved, target.resolve())
        self.assertTrue(str(resolved).startswith(str(storage_service.control_results_dir.resolve())))

    def test_control_result_parent_and_absolute_rejected(self) -> None:
        escaped = control_result_photo_service.absolute_photo_path(
            "../outside/SENTINEL.txt"
        )
        self.assertFalse(escaped.is_file())
        absolute = control_result_photo_service.absolute_photo_path(str(self.sentinel))
        self.assertFalse(absolute.is_file())
        self.assertTrue(self.sentinel.is_file())

    def test_control_result_delete_does_not_remove_sentinel(self) -> None:
        control_result_photo_service.delete_photo(str(self.sentinel))
        control_result_photo_service.delete_photo("../outside/SENTINEL.txt")
        control_result_photo_service.delete_photo("control_results/../../outside/SENTINEL.txt")
        self.assertTrue(self.sentinel.is_file())

    def test_control_result_delete_skips_symlink_out(self) -> None:
        link = storage_service.control_results_dir / "audity" / "1" / "photo.jpg"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(self.sentinel)
        control_result_photo_service.delete_photo(
            "control_results/audity/1/photo.jpg"
        )
        self.assertTrue(self.sentinel.is_file())

    def test_coordination_ordinary_and_rejected_paths(self) -> None:
        stored = self._write_inside("coordination/4/employer_2/rizika.pdf")
        row = SimpleNamespace(file_path="coordination/4/employer_2/rizika.pdf")
        resolved = coordination_attachment_service.resolve_path(row)
        self.assertEqual(resolved, stored.resolve())

        row.file_path = str(self.sentinel)
        with self.assertRaises(CoordinationAttachmentError):
            coordination_attachment_service.resolve_path(row)

        row.file_path = "../outside/SENTINEL.txt"
        with self.assertRaises(CoordinationAttachmentError):
            coordination_attachment_service.resolve_path(row)
        self.assertTrue(self.sentinel.is_file())

    def test_pbp_ordinary_and_rejected_paths(self) -> None:
        stored = self._write_inside("coordination_pbp/5/PBP.odt")
        revision = SimpleNamespace(file_path="coordination_pbp/5/PBP.odt")
        resolved = coordination_pbp_attachment_service.resolve_path(revision)
        self.assertEqual(resolved, stored.resolve())

        revision.file_path = str(self.sentinel)
        with self.assertRaises(CoordinationPbpAttachmentError):
            coordination_pbp_attachment_service.resolve_path(revision)

        revision.file_path = "../../outside/SENTINEL.txt"
        with self.assertRaises(CoordinationPbpAttachmentError):
            coordination_pbp_attachment_service.resolve_path(revision)
        self.assertTrue(self.sentinel.is_file())

    def test_hazard_relative_path_confined_to_prilohy(self) -> None:
        stored = self._write_inside("rizeni_rizik/ID-1/fotografie/a.jpg")
        photo = SimpleNamespace(relative_path="rizeni_rizik/ID-1/fotografie/a.jpg")
        self.assertEqual(
            hazard_identification_photo_service.absolute_path(photo),
            stored.resolve(),
        )
        photo.relative_path = str(self.sentinel)
        self.assertFalse(hazard_identification_photo_service.absolute_path(photo).is_file())
        photo.relative_path = "../outside/SENTINEL.txt"
        self.assertFalse(hazard_identification_photo_service.file_exists(photo))
        self.assertTrue(self.sentinel.is_file())

    def test_add_file_as_does_not_write_outside_on_traversal_filename(self) -> None:
        source = self.tmp / "zdroj.txt"
        source.write_text("payload", encoding="utf-8")
        escaped = self.outside / "ESCAPED.txt"
        created = self.service.add_file_as(
            "task",
            7,
            str(source),
            "../../../outside/ESCAPED.txt",
        )
        self.assertIsNotNone(created)
        self.assertFalse(escaped.exists())
        stored = self.service.resolve_path(created)
        stored.relative_to(storage_service.attachments_dir.resolve())
        self.assertEqual(created.filename, "ESCAPED.txt")
        self.assertTrue(stored.is_file())

    def test_add_file_rejects_traversing_entity_type(self) -> None:
        source = self.tmp / "zdroj2.txt"
        source.write_text("payload", encoding="utf-8")
        created = self.service.add_file(
            "../../outside",
            8,
            str(source),
        )
        self.assertIsNone(created)
        self.assertFalse((self.outside / "8").exists())
        self.assertTrue(self.sentinel.is_file())
        leaked = list(self.outside.rglob("*"))
        self.assertEqual(leaked, [self.sentinel])


if __name__ == "__main__":
    unittest.main()
