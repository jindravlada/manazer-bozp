"""SEC-12a: referenční fotografie auditů a prověrek nesmí opustit své úložiště."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_method_support_photo_service import (
    absolute_support_photo_path,
    freeze_reference_photos_in_payload,
)
from moduly.audity.sluzby.audit_reference_photo_service import (
    audit_reference_photo_service,
)
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
from moduly.proverky.sluzby.proverky_reference_photo_service import (
    proverky_reference_photo_service,
)

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"


class Sec12aReferencePhotoConfinementTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _TEST_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="sec12a-", dir=_TEST_ROOT))
        self.workspace = self.tmp / "workspace"
        self.outside_dir = self.tmp / "outside"
        self.workspace.mkdir()
        self.outside_dir.mkdir()
        self.outside = self.outside_dir / "outside.jpg"
        self.outside.write_bytes(b"CANARY-SEC-12A")
        (self.workspace / "ciselniky" / "audity" / "fotografie").mkdir(parents=True)
        (self.workspace / "ciselniky" / "proverky" / "fotografie").mkdir(parents=True)
        (self.workspace / "snapshot_support_photos").mkdir()
        self._orig_bases: list[tuple[object, Path]] = []
        for module in list(sys.modules.values()):
            svc = getattr(module, "storage_service", None)
            if svc is None or not hasattr(svc, "base"):
                continue
            if any(item is svc for item, _base in self._orig_bases):
                continue
            self._orig_bases.append((svc, svc.base))
            svc.base = self.workspace

    def tearDown(self) -> None:
        for svc, base in self._orig_bases:
            svc.base = base
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_inside(self, root: Path, relative: str, data: bytes = b"inside") -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.resolve()

    def _assert_rejected(self, resolved: Path) -> None:
        self.assertEqual(resolved, Path())
        self.assertTrue(self.outside.is_file())
        self.assertEqual(self.outside.read_bytes(), b"CANARY-SEC-12A")

    def _escape_values(self) -> list[str]:
        return [
            str(self.outside),
            "../../outside.jpg",
            "fotografie/../../../outside.jpg",
        ]

    def test_audit_rejects_absolute_parent_and_nested_escape(self) -> None:
        for value in self._escape_values():
            with self.subTest(value=value):
                self._assert_rejected(
                    audit_reference_photo_service.absolute_photo_path(value)
                )

    def test_proverky_rejects_absolute_parent_and_nested_escape(self) -> None:
        for value in self._escape_values():
            with self.subTest(value=value):
                self._assert_rejected(
                    proverky_reference_photo_service.absolute_photo_path(value)
                )

    def test_audit_rejects_symlink_pointing_outside(self) -> None:
        link = audit_knowledge_service.audity_dir / "fotografie" / "odkaz.jpg"
        link.symlink_to(self.outside)
        self._assert_rejected(
            audit_reference_photo_service.absolute_photo_path("fotografie/odkaz.jpg")
        )

    def test_proverky_rejects_symlink_pointing_outside(self) -> None:
        link = proverky_knowledge_service.proverky_dir / "fotografie" / "odkaz.jpg"
        link.symlink_to(self.outside)
        self._assert_rejected(
            proverky_reference_photo_service.absolute_photo_path("fotografie/odkaz.jpg")
        )

    def test_snapshot_escape_is_rejected_against_snapshot_root(self) -> None:
        self._assert_rejected(
            audit_reference_photo_service.absolute_photo_path(
                "snapshot_support_photos/../../outside.jpg"
            )
        )
        self._assert_rejected(
            absolute_support_photo_path("snapshot_support_photos/../../outside.jpg")
        )

    def test_ordinary_relative_photos_are_allowed(self) -> None:
        audit_file = self._write_inside(
            audit_knowledge_service.audity_dir,
            "fotografie/proc/crit/ok.jpg",
        )
        proverky_file = self._write_inside(
            proverky_knowledge_service.proverky_dir,
            "fotografie/area/sec/ok.jpg",
        )
        self.assertEqual(
            audit_reference_photo_service.absolute_photo_path(
                "fotografie/proc/crit/ok.jpg"
            ),
            audit_file,
        )
        self.assertEqual(
            proverky_reference_photo_service.absolute_photo_path(
                "fotografie/area/sec/ok.jpg"
            ),
            proverky_file,
        )

    def test_ordinary_snapshot_support_photo_is_allowed(self) -> None:
        snap = self._write_inside(
            self.workspace / "snapshot_support_photos",
            "ab/hash.jpg",
            b"snap-ok",
        )
        rel = "snapshot_support_photos/ab/hash.jpg"
        self.assertEqual(
            audit_reference_photo_service.absolute_photo_path(rel),
            snap,
        )
        self.assertEqual(absolute_support_photo_path(rel), snap)

    def test_proverky_delete_does_not_remove_outside_canary(self) -> None:
        values = self._escape_values() + ["fotografie/odkaz.jpg"]
        link = proverky_knowledge_service.proverky_dir / "fotografie" / "odkaz.jpg"
        link.symlink_to(self.outside)
        for value in values:
            with self.subTest(value=value):
                proverky_reference_photo_service.delete_photo(value)
                self.assertTrue(self.outside.is_file())
                self.assertEqual(self.outside.read_bytes(), b"CANARY-SEC-12A")

    def test_audit_delete_does_not_remove_outside_canary(self) -> None:
        values = self._escape_values() + ["fotografie/odkaz.jpg"]
        link = audit_knowledge_service.audity_dir / "fotografie" / "odkaz.jpg"
        link.symlink_to(self.outside)
        for value in values:
            with self.subTest(value=value):
                audit_reference_photo_service.delete_photo(value)
                self.assertTrue(self.outside.is_file())
                self.assertEqual(self.outside.read_bytes(), b"CANARY-SEC-12A")

    def test_freeze_does_not_copy_file_outside_root(self) -> None:
        payload = {
            "section": {
                "referencni_fotografie": [
                    {"id": "evil", "nazev": "Evil", "soubor": str(self.outside)},
                    {
                        "id": "escape",
                        "nazev": "Escape",
                        "soubor": "snapshot_support_photos/../../outside.jpg",
                    },
                ]
            }
        }
        copied: list[Path] = []
        real_copy2 = shutil.copy2

        def _guarded_copy2(src, dst, *args, **kwargs):
            src_path = Path(src).resolve()
            copied.append(src_path)
            if src_path == self.outside.resolve():
                self.fail("freeze zkopíroval soubor mimo povolený root")
            return real_copy2(src, dst, *args, **kwargs)

        staging = Path(tempfile.mkdtemp(prefix="sec12a-stage-", dir=self.tmp))
        with patch(
            "moduly.audity.sluzby.audit_method_support_photo_service.shutil.copy2",
            side_effect=_guarded_copy2,
        ):
            frozen, staged = freeze_reference_photos_in_payload(
                payload, staging_dir=staging
            )
        photos = frozen["section"]["referencni_fotografie"]
        self.assertTrue(photos[0].get("missing"))
        self.assertTrue(photos[1].get("missing"))
        self.assertEqual(staged, [])
        self.assertEqual(copied, [])
        self.assertTrue(self.outside.is_file())
        self.assertEqual(self.outside.read_bytes(), b"CANARY-SEC-12A")

    def test_freeze_copies_confined_methodology_photo(self) -> None:
        source = self._write_inside(
            audit_knowledge_service.audity_dir,
            "fotografie/proc/crit/ok.jpg",
            b"\xff\xd8\xff\xe0confined-ok",
        )
        payload = {
            "section": {
                "referencni_fotografie": [
                    {
                        "id": "ok",
                        "nazev": "Ok",
                        "soubor": "fotografie/proc/crit/ok.jpg",
                    }
                ]
            }
        }
        staging = Path(tempfile.mkdtemp(prefix="sec12a-ok-", dir=self.tmp))
        frozen, staged = freeze_reference_photos_in_payload(
            payload, staging_dir=staging
        )
        photo = frozen["section"]["referencni_fotografie"][0]
        self.assertFalse(photo.get("missing"))
        self.assertTrue(photo["soubor"].startswith("snapshot_support_photos/"))
        self.assertEqual(len(staged), 1)
        self.assertTrue(staged[0].is_file())
        self.assertEqual(source.read_bytes(), b"\xff\xd8\xff\xe0confined-ok")

    def test_save_optimized_stores_relative_path_and_leaves_original(self) -> None:
        original = self.outside_dir / "picked.jpg"
        Image.new("RGB", (32, 24), color=(12, 34, 56)).save(original, format="JPEG")
        original_bytes = original.read_bytes()
        relative = audit_reference_photo_service.save_optimized(
            original,
            process_id="proc",
            criterion_id="crit",
            photo_id="photo1",
        )
        self.assertFalse(Path(relative).is_absolute())
        stored = audit_reference_photo_service.absolute_photo_path(relative)
        self.assertTrue(stored.is_file())
        self.assertTrue(
            stored.resolve().is_relative_to(
                audit_knowledge_service.audity_dir.resolve()
            )
        )
        self.assertEqual(original.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
